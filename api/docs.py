"""The API reference page, served entirely from this origin.

PRD section 13 requires that the application run with no network beyond
localhost and that every asset be self-hosted. FastAPI's own `/docs` page was
the one place that never honoured it: the HTML it generates hardcodes
`swagger-ui.css` and `swagger-ui-bundle.js` on cdn.jsdelivr.net and a favicon on
fastapi.tiangolo.com. Under this application's `default-src 'none'` policy the
browser blocked all three plus the inline bootstrap script, and the page
rendered blank with four console violations — on localhost exactly as on a
deployment.

So the page is built here instead, against vendored assets in
`api/swagger_assets/`. The bootstrap lives in `docs-init.js` rather than an
inline <script>, which is what lets `script-src` stay `'self'` with no
'unsafe-inline', no hash and no nonce.

As in FastAPI, this is a development affordance: it is not mounted when
GCPL_ENV=prod.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from .config import settings

ASSETS = Path(__file__).resolve().parent / "swagger_assets"

DOCS_PATH = "/docs"
ASSETS_PATH = "/docs-assets"

# P1 to P10, as the scope model defines them. The selector is part of the page
# rather than a note telling the reader to add a header by hand.
PERSONAS: tuple[tuple[str, str], ...] = (
    ("P1", "CFO"),
    ("P2", "Group Treasurer"),
    ("P3", "Front Office Dealer"),
    ("P4", "Regional Lead"),
    ("P5", "Local Coordinator"),
    ("P6", "Risk and Control Analyst"),
    ("P7", "Operations Specialist"),
    ("P8", "Internal Auditor"),
    ("P9", "IT Administrator"),
    ("P10", "Tax and Legal Counsel"),
)


def _options(selected: str = "P2") -> str:
    return "".join(
        f'<option value="{code}"{" selected" if code == selected else ""}>'
        f"{code} · {name}</option>"
        for code, name in PERSONAS
    )


def _page() -> str:
    return f"""<!doctype html>
<html lang="en-GB">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="robots" content="noindex, nofollow" />
    <title>GCPL Treasury Command — API reference</title>
    <link rel="stylesheet" href="{ASSETS_PATH}/swagger-ui.css" />
    <style>
      body {{ margin: 0; background: #fafafa; }}
      .gcpl-bar {{
        display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
        padding: 12px 20px; background: #161616; color: #f4f4f4;
        font: 13px/1.5 system-ui, sans-serif;
      }}
      .gcpl-bar strong {{ font-weight: 600; }}
      .gcpl-bar .note {{ color: #8d8d8d; }}
      .gcpl-bar select {{
        background: #262626; color: #f4f4f4; border: 1px solid #525252;
        border-radius: 4px; padding: 4px 8px; font: inherit;
      }}
      .gcpl-ribbon {{
        padding: 8px 20px; background: #2d1518; color: #ffb3b8;
        font: 11px/1.5 system-ui, sans-serif; letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
    </style>
  </head>
  <body>
    <div class="gcpl-bar">
      <strong>GCPL Treasury Command</strong>
      <span class="note">Phase 0 control layer · this API moves no money</span>
      <label for="persona">Acting persona</label>
      <select id="persona" aria-label="Acting persona sent as X-Persona">
        {_options()}
      </select>
      <span class="note">
        Sent as <code>X-Persona</code> on every request below. Scope is resolved
        on the server; an out-of-scope entity returns 403, not a filtered 200.
      </span>
    </div>
    <div class="gcpl-ribbon">
      Synthetic data // demo tenant for EY CAFTA 2026 // do not rely for live transfers
    </div>
    <div id="swagger-ui"></div>
    <script src="{ASSETS_PATH}/swagger-ui-bundle.js"></script>
    <script src="{ASSETS_PATH}/docs-init.js"></script>
  </body>
</html>
"""


def mount_docs(app: FastAPI) -> bool:
    """Serve the reference page and its assets. Returns whether it was mounted.

    Mounted before the SPA so that `/docs` and `/docs-assets` are matched by
    these routes rather than falling through to the app shell.
    """
    # One source of truth for "are docs open here": the same property FastAPI
    # was given before, which is None in prod.
    if settings.docs_url is None:
        return False
    if not (ASSETS / "swagger-ui-bundle.js").is_file():
        return False

    app.mount(
        ASSETS_PATH,
        StaticFiles(directory=ASSETS),
        name="swagger-assets",
    )

    @app.get(DOCS_PATH, include_in_schema=False, response_class=HTMLResponse)
    async def api_reference() -> HTMLResponse:
        return HTMLResponse(_page())

    return True
