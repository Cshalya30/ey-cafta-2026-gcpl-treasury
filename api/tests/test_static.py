"""Serving the built app from the API process.

These guard the hosting story. The failure they exist to catch is quiet: the
API's `default-src 'none'` policy applied to the document renders a blank page
with the app's own bundle blocked, and nothing in the API tests would notice.
"""

from __future__ import annotations

import pytest

from api.config import Settings
from api.security import APP_CSP, API_CSP
from api.static import DIST

from .conftest import headers

needs_build = pytest.mark.skipif(
    not (DIST / "index.html").is_file(),
    reason="web/dist is absent. Run: cd web && npm run build",
)


# ───────────────────────── the two content security policies ─────────────────


def test_the_api_policy_forbids_every_source(client):
    """The API embeds nothing, so it may refuse everything."""
    for path in ("/health", "/api/v1/state", "/api/v1/nope"):
        csp = client.get(path, headers=headers("P2")).headers["Content-Security-Policy"]
        assert csp == API_CSP
        assert "default-src 'none'" in csp


@needs_build
def test_the_app_policy_allows_the_app_to_load_itself(client):
    """`default-src 'none'` on the document would block the bundle silently."""
    csp = client.get("/").headers["Content-Security-Policy"]
    assert csp == APP_CSP
    assert "script-src 'self'" in csp
    assert "default-src 'none'" not in csp


def test_the_app_policy_never_loosens_script_execution():
    """'unsafe-inline' is for style attributes only; scripts keep no escape."""
    directives = dict(
        part.strip().split(" ", 1) for part in APP_CSP.split(";") if " " in part.strip()
    )
    assert directives["script-src"] == "'self'"
    assert "unsafe-eval" not in APP_CSP
    assert "'unsafe-inline'" in directives["style-src"]
    assert directives["frame-ancestors"] == "'none'"
    assert directives["object-src"] == "'none'"


@needs_build
def test_hardening_headers_survive_the_static_mount(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


# ───────────────────────── client-side routing ─────────────────────────


@needs_build
@pytest.mark.parametrize(
    "path", ["/", "/console", "/brief", "/canvas/pooling", "/cockpit/GCPL-GB"]
)
def test_a_deep_link_returns_the_app_shell(client, path):
    """A judge who reloads on /cockpit/GCPL-GB must not get a 404."""
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in response.text


@needs_build
def test_public_files_are_served_as_themselves(client):
    """robots.txt must be the file, not the shell with a 200 on it."""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "Disallow: /" in response.text
    assert "<html" not in response.text.lower()


# ───────────────────────── the API keeps its own 404 ─────────────────────────


@needs_build
def test_an_unknown_api_path_is_a_problem_document_not_the_shell(client):
    response = client.get("/api/v1/nope", headers=headers("P2"))
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "No such endpoint."


@needs_build
def test_a_missing_asset_is_a_404_rather_than_html(client):
    """Falling back here would cache the shell under a .js URL for a year."""
    response = client.get("/assets/does-not-exist-x9.js")
    assert response.status_code == 404
    assert "<html" not in response.text.lower()


# ───────────────────────── caching ─────────────────────────


@needs_build
def test_only_real_hashed_assets_are_cacheable(client):
    import re

    shell = client.get("/").text
    asset = re.search(r'src="(/assets/[^"]+\.js)"', shell).group(1)

    served = client.get(asset)
    assert served.status_code == 200
    assert served.headers["Cache-Control"] == "public, max-age=31536000, immutable"

    # The shell itself must not be, or a redeploy is invisible until expiry.
    assert client.get("/").headers["Cache-Control"] == "no-store"
    # Nor may a miss be pinned in the cache.
    assert client.get("/assets/gone-x9.js").headers["Cache-Control"] == "no-store"


def test_figures_from_the_api_are_never_cacheable(client):
    assert client.get("/api/v1/state", headers=headers("P2")).headers[
        "Cache-Control"
    ] == "no-store"


# ───────────────────────── the health probe ─────────────────────────


def test_the_health_probe_is_exempt_from_the_https_redirect(client, monkeypatch):
    """A platform probe arrives on plain HTTP; redirecting it loops restarts."""
    import api.security

    monkeypatch.setenv("GCPL_FORCE_HTTPS", "1")
    monkeypatch.setattr(api.security, "settings", Settings())

    probe = client.get("/health")
    assert probe.status_code == 200
    assert probe.json()["status"] == "ok"

    # Everything else still redirects.
    redirected = client.get("/api/v1/state", headers=headers("P2"), follow_redirects=False)
    assert redirected.status_code == 308


@needs_build
@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
def test_no_method_on_an_unknown_api_path_reaches_the_shell(client, method):
    """An uptime monitor usually probes with HEAD.

    FastAPI does not derive HEAD from GET, so a route declaring only GET lets
    HEAD fall through to the static mount, which answers 200 text/html for
    anything. A monitor would then report a dead API as healthy.
    """
    response = client.request(method, "/api/v1/nope", headers=headers("P2"))
    assert response.status_code == 404
    assert not response.headers["content-type"].startswith("text/html")


def test_json_surfaces_are_classified_as_api(client):
    """The JSON surfaces embed nothing, so they take default-src 'none'."""
    from api.security import _is_api_path

    for path in ("/health", "/redoc", "/openapi.json", "/api/v1/state"):
        assert _is_api_path(path), path
    for path in ("/", "/console", "/robots.txt", "/assets/index.js", "/docs"):
        assert not _is_api_path(path), path


# ───────────────────────── the API reference page ─────────────────────────


def test_the_reference_page_loads_nothing_from_a_cdn(client):
    """PRD 13: no network beyond localhost. FastAPI's own page broke this.

    The failure it replaced was silent: the stylesheet, the bundle and the
    favicon all came from third-party hosts, the policy blocked them, and the
    page rendered blank with no server-side error.
    """
    body = client.get("/docs").text
    assert body, "the reference page must be served"
    for host in ("cdn.jsdelivr.net", "fastapi.tiangolo.com", "unpkg.com", "//cdn."):
        assert host not in body, f"{host} is reachable from the reference page"
    assert "/docs-assets/swagger-ui.css" in body
    assert "/docs-assets/swagger-ui-bundle.js" in body


def test_the_reference_page_has_no_inline_script(client):
    """What lets script-src stay 'self' with no hash, nonce or unsafe-inline."""
    import re

    body = client.get("/docs").text
    for script in re.findall(r"<script\b[^>]*>(.*?)</script>", body, re.S):
        assert not script.strip(), "an inline script would need a CSP escape"


def test_the_reference_page_gets_its_own_policy(client):
    from api.security import API_CSP, DOCS_CSP

    csp = client.get("/docs").headers["Content-Security-Policy"]
    assert csp == DOCS_CSP
    assert csp != API_CSP, "default-src 'none' renders this page blank"
    # Parse per directive. Splitting on the text "style-src" would miss an
    # 'unsafe-inline' added to a script-src that came after it.
    directives = {
        part.strip().split(" ", 1)[0]: part.strip().split(" ", 1)[1]
        for part in csp.split(";")
        if " " in part.strip()
    }
    assert directives["script-src"] == "'self'"
    for name, value in directives.items():
        if name != "style-src":
            assert "'unsafe-inline'" not in value, f"{name} must not be inline-permissive"


def test_the_vendored_assets_are_served(client):
    for path, kind in (
        ("/docs-assets/swagger-ui.css", "css"),
        ("/docs-assets/swagger-ui-bundle.js", "javascript"),
        ("/docs-assets/docs-init.js", "javascript"),
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert kind in response.headers["content-type"]


def test_the_reference_page_sends_the_persona_header(client):
    """Without it every Try it out answers 422 and teaches nothing."""
    init = client.get("/docs-assets/docs-init.js").text
    assert "X-Persona" in init
    assert "requestInterceptor" in init
    page = client.get("/docs").text
    assert 'id="persona"' in page
    for code in ("P1", "P5", "P10"):
        assert f'value="{code}"' in page


def test_the_reference_page_is_closed_in_production(monkeypatch):
    """It is a development affordance, exactly as FastAPI's own page was."""
    import api.config
    import api.docs

    monkeypatch.setenv("GCPL_ENV", "prod")
    monkeypatch.setattr(api.docs, "settings", api.config.Settings())

    from fastapi import FastAPI

    assert api.docs.mount_docs(FastAPI()) is False


def test_the_reference_page_disables_the_online_validator(client):
    """The one third-party call that only appears off localhost.

    Swagger defaults validatorUrl to validator.swagger.io and renders a badge
    that calls it with this API's spec URL attached. The badge is suppressed
    when the spec URL is localhost, so every local check would pass while the
    deployment — the only place a judge looks — reached a third party.
    """
    init = client.get("/docs-assets/docs-init.js").text
    assert "validatorUrl: null" in init
    assert "validator.swagger.io" not in init.replace(
        "https://validator.swagger.io/validator", ""
    ), "the only mention may be the comment explaining why it is disabled"
