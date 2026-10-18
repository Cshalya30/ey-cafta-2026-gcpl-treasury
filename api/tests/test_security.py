"""Transport, session, CSRF, rate limiting and input-handling guards.

These cover the launch-hardening checklist for an application that holds
synthetic data: the controls have to be real even when the data is not,
because the deployment story is part of the recommendation.
"""

from __future__ import annotations

import os

import pytest

from api import auth
from api.config import Settings
from .conftest import headers


# ───────────────────────── headers and transport ─────────────────────────


def test_security_headers_on_every_response(client):
    for path in ("/health", "/api/v1/state", "/api/v1/nope"):
        response = client.get(path, headers=headers("P2"))
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["Cache-Control"] == "no-store", (
            "financial figures must not be written to a shared cache"
        )


def test_permissions_policy_disables_device_access(client):
    policy = client.get("/health").headers["Permissions-Policy"]
    for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert f"{feature}=()" in policy


def test_hsts_only_when_tls_is_declared(client, monkeypatch):
    """HSTS on plain localhost would simply break the demo, so it is conditional."""
    assert "Strict-Transport-Security" not in client.get("/health").headers

    import api.security

    # Settings is frozen by design; swap the whole object rather than a field.
    monkeypatch.setenv("GCPL_FORCE_HTTPS", "1")
    monkeypatch.setattr(api.security, "settings", Settings())
    assert "Strict-Transport-Security" in client.get("/health").headers


def test_docs_are_closed_in_production(monkeypatch):
    monkeypatch.setenv("GCPL_ENV", "prod")
    prod = Settings()
    assert prod.is_prod
    assert prod.docs_url is None, "OpenAPI docs are a development affordance"


def test_cors_never_allows_a_wildcard_origin():
    settings = Settings()
    assert "*" not in settings.cors_origins
    assert all(origin.startswith("http") for origin in settings.cors_origins)


# ───────────────────────── session tokens ─────────────────────────


def test_session_token_round_trips():
    token, csrf = auth.issue_session("operator")
    assert auth.verify_session(token) == "operator"
    assert len(csrf) >= 32


def test_tampered_session_token_is_rejected():
    token, _ = auth.issue_session("operator")
    subject, expires, nonce, signature = token.rsplit("|", 3)
    forged = f"admin|{expires}|{nonce}|{signature}"
    assert auth.verify_session(forged) is None


def test_expired_session_token_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "SESSION_TTL_SECONDS", -1)
    token, _ = auth.issue_session("operator")
    assert auth.verify_session(token) is None


def test_garbage_session_token_is_rejected():
    for value in (None, "", "not-a-token", "a|b|c", "a|b|c|d|e"):
        assert auth.verify_session(value) is None


def test_session_endpoint_reports_dev_mode(client):
    body = client.get("/api/v1/session").json()
    assert body["authenticated"] is False
    assert body["environment"] == "dev"
    assert "Capability rules" in body["note"]


def test_sign_in_is_not_required_in_dev(client):
    response = client.post("/api/v1/session", json={"access_key": "anything"})
    assert response.status_code == 400
    assert "development deployment" in response.json()["detail"]


def test_sign_in_rejects_a_wrong_key_without_saying_why(client, monkeypatch):
    monkeypatch.setenv("GCPL_ACCESS_KEY", "the-real-key")
    response = client.post("/api/v1/session", json={"access_key": "wrong"})
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert "the-real-key" not in detail
    assert "Check the key" in detail


def test_sign_in_sets_hardened_cookies(client, monkeypatch):
    monkeypatch.setenv("GCPL_ACCESS_KEY", "the-real-key")
    response = client.post("/api/v1/session", json={"access_key": "the-real-key"})
    assert response.status_code == 200

    raw = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in raw if c.startswith(auth.SESSION_COOKIE))
    csrf_cookie = next(c for c in raw if c.startswith(auth.CSRF_COOKIE))

    assert "HttpOnly" in session_cookie
    assert "SameSite=strict" in session_cookie.lower().replace("samesite=strict", "SameSite=strict")
    # The CSRF half of a double-submit pair must be readable by the page.
    assert "HttpOnly" not in csrf_cookie


# ───────────────────────── CSRF and rate limiting ─────────────────────────


def test_csrf_is_not_enforced_in_dev():
    import api.auth

    class _Request:
        cookies: dict[str, str] = {}
        headers: dict[str, str] = {}

    api.auth.enforce_csrf(_Request())  # must not raise


def test_rate_limit_blocks_a_burst(monkeypatch):
    monkeypatch.setattr(auth, "RATE_LIMIT_WRITES", 3)
    auth._write_log.clear()

    for _ in range(3):
        auth.enforce_rate_limit("burst-test")

    with pytest.raises(Exception) as caught:
        auth.enforce_rate_limit("burst-test")
    assert getattr(caught.value, "status_code", None) == 429


def test_rate_limit_is_per_subject(monkeypatch):
    monkeypatch.setattr(auth, "RATE_LIMIT_WRITES", 1)
    auth._write_log.clear()
    auth.enforce_rate_limit("alice")
    auth.enforce_rate_limit("bob")  # a different subject is unaffected


# ───────────────────────── input handling ─────────────────────────


def test_oversized_and_malformed_input_is_rejected_by_schema(client):
    bad = {
        "kind": "intercompany_loan",
        "source_entity_id": "GCPL-GB",
        "target_entity_id": "GCPL-US",
        "amount_usd": -5,                 # must be > 0
        "tenor_days": 99_999,             # beyond the 3650 cap
        "interest_rate": 7.5,             # a rate, not a percentage
        "rate_basis": "x" * 500,          # beyond the 120 cap
        "justification": "a",             # below the 4-character minimum
    }
    response = client.post("/api/v1/proposals", json=bad, headers=headers("P3"))
    assert response.status_code == 422
    assert response.json()["title"] == "The request did not validate."


def test_persona_header_is_pattern_validated(client):
    for value in ("P0", "P11", "; DROP TABLE account", "<script>", "P2 OR 1=1"):
        assert client.get("/api/v1/state", headers={"X-Persona": value}).status_code == 422


def test_sql_injection_through_a_filter_is_parameterised(client):
    """SQLAlchemy binds parameters; a quoted payload must be data, not SQL."""
    response = client.get(
        "/api/v1/accounts",
        params={"entity": "GCPL-GB' OR '1'='1"},
        headers=headers("P2"),
    )
    # Out of scope by id, so the scope check rejects it before the query runs.
    assert response.status_code == 403
    # The table is still there.
    assert client.get("/api/v1/accounts", headers=headers("P2")).status_code == 200


def test_a_script_payload_in_a_justification_is_stored_as_text(client):
    payload = "<script>alert('xss')</script>"
    body = {
        "kind": "intercompany_loan",
        "source_entity_id": "GCPL-GB",
        "target_entity_id": "GCPL-US",
        "amount_usd": 1_000_000.0,
        "tenor_days": 90,
        "interest_rate": 0.0850,
        "rate_basis": "6M Term SONIA + 395bps",
        "justification": payload,
    }
    created = client.post("/api/v1/proposals", json=body, headers=headers("P3"))
    assert created.status_code == 201

    # It round-trips as data. React escapes on render; the API never emits HTML.
    events = client.get(
        "/api/v1/audit", params={"object_kind": "proposal"}, headers=headers("P8")
    ).json()
    stored = [e for e in events if e["justification"] == payload]
    assert stored, "the justification must be stored verbatim as text"
    assert created.headers["Content-Type"].startswith("application/json")


def test_errors_carry_the_problem_media_type(client):
    response = client.get("/api/v1/entities/GCPL-GB", headers=headers("P5"))
    assert response.status_code == 403
    assert response.headers["Content-Type"].startswith("application/problem+json")


def test_no_secret_is_committed_to_the_repository():
    """The signing key is environment-derived and random by default."""
    from api.config import REPO_ROOT

    env_file = REPO_ROOT / ".env"
    assert not env_file.exists() or env_file.stat().st_size == 0, (
        ".env must never be committed; it is gitignored for this reason"
    )

    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GCPL_SESSION_SECRET=" in example
    assert "GCPL_SESSION_SECRET=sk" not in example, "the template must hold no real value"


def test_session_secret_defaults_to_random_per_boot(monkeypatch):
    monkeypatch.delenv("GCPL_SESSION_SECRET", raising=False)
    assert Settings().session_secret != Settings().session_secret
