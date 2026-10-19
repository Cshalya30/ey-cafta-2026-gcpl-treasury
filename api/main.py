"""GCPL Treasury Command API.

A Phase 0 control layer. It proposes, validates and records. It never moves
money, holds no payment credentials, and carries synthetic data only.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .db import get_engine, init_db
from .routers import banking, entities, forecasts, governance, pooling, session, state
from .security import HttpsRedirectMiddleware, SecurityHeadersMiddleware
from .static import mount_spa

API_PREFIX = "/api/v1"

DESCRIPTION = """
The future-state treasury operating model of Global Consumer Products Ltd,
rendered executable.

**This is not a Treasury Management System.** It is a Phase 0 control layer and
a TMS requirements specification. It initiates no payments and is not a system
of record. All data is synthetic.

Every request must carry an `X-Persona` header (P1 to P10). Scope is resolved
from that persona on the server; it is never filtered in the browser. An
out-of-scope entity returns 403, not a filtered 200.
"""

app = FastAPI(
    title="GCPL Treasury Command",
    version="2.0.0",
    description=DESCRIPTION,
    docs_url=settings.docs_url,
    redoc_url=None,
    openapi_url=None if settings.is_prod else "/openapi.json",
)

# Order matters: the outermost middleware is added last, so the HTTPS redirect
# runs before anything else and the security headers are attached to whatever
# comes back, including a redirect or an error.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    # Exact origins only. A wildcard here would let any page on the machine read
    # persona-scoped financial data.
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-Persona", "Content-Type", "X-CSRF-Token"],
    max_age=600,
)
app.add_middleware(HttpsRedirectMiddleware)


@app.on_event("startup")
def _startup() -> None:
    init_db(get_engine())


@app.on_event("shutdown")
def _shutdown() -> None:
    get_engine().dispose()


# ───────────────────────── RFC 9457 problem details ─────────────────────────


def _problem(status_code: int, title: str, detail: str, instance: str | None, type_: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        },
        media_type="application/problem+json",
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Routers raise either a ready-made problem dict or a plain string."""
    if isinstance(exc.detail, dict) and "title" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            media_type="application/problem+json",
        )
    return _problem(
        exc.status_code,
        str(exc.detail) if exc.detail else "Request failed.",
        str(exc.detail) if exc.detail else "",
        str(request.url.path),
        "about:blank",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Say which field failed and why. Never echo the submitted value back."""
    fields = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())[1:])
        fields.append(f"{location or 'body'}: {error.get('msg', 'invalid')}")
    return _problem(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "The request did not validate.",
        " ".join(fields),
        str(request.url.path),
        "https://gcpl.local/problems/validation",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak a stack trace or a file path to the client."""
    return _problem(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "The request could not be completed.",
        "An unexpected error occurred. The request was not applied.",
        str(request.url.path),
        "https://gcpl.local/problems/internal",
    )


# ───────────────────────── routes ─────────────────────────

for module in (state, entities, banking, forecasts, pooling, governance, session):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok", "environment": settings.env, "moves_money": False}


# The built app is mounted last so that every API route and /health is matched
# before the root catch-all. Returns False when web/dist is absent, which is the
# normal state in development and under pytest: the API then runs alone and the
# Vite dev server proxies /api to it.
SERVING_APP = mount_spa(app)
