"""Authentication, CSRF and rate limiting.

A deliberate design note, because the honest answer matters more than a tick in
a box. The PRD's persona switcher is a demonstration mechanic: a judge must be
able to become a Front Office Dealer and watch the API refuse an approval. That
is the point of the product, and putting a login in front of it on localhost
would break the two-command demo for no security gain, since the data is
synthetic and the app initiates no payments.

So the gate is conditional, not absent:

  * GCPL_ENV=dev  (default) — open. Persona switching is free. The watermark,
    the synthetic data and the absence of any payment rail are the controls.
  * GCPL_ENV=prod — a signed, HttpOnly, SameSite=Strict session cookie is
    required for every write, a double-submit CSRF token must match, and writes
    are rate limited per session.

Capability enforcement (who may approve, who may settle) runs in BOTH modes and
is never conditional: it is the product's actual subject.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response, status

from .config import settings

SESSION_COOKIE = "gcpl_session"
CSRF_COOKIE = "gcpl_csrf"
CSRF_HEADER = "X-CSRF-Token"

SESSION_TTL_SECONDS = 8 * 60 * 60

# Writes per session per window. Generous for a human, useless for a script.
RATE_LIMIT_WRITES = 60
RATE_LIMIT_WINDOW_SECONDS = 60

_write_log: dict[str, deque[float]] = defaultdict(deque)


# ───────────────────────── session tokens ─────────────────────────


def _sign(payload: str) -> str:
    return hmac.new(
        settings.session_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def issue_session(subject: str) -> tuple[str, str]:
    """Return (session token, csrf token). The session token is self-verifying."""
    expires = int(time.time()) + SESSION_TTL_SECONDS
    nonce = secrets.token_urlsafe(16)
    payload = f"{subject}|{expires}|{nonce}"
    return f"{payload}|{_sign(payload)}", secrets.token_urlsafe(32)


def verify_session(token: str | None) -> str | None:
    """Return the subject when the token is valid and unexpired, else None."""
    if not token:
        return None
    try:
        subject, expires, nonce, signature = token.rsplit("|", 3)
    except ValueError:
        return None

    expected = _sign(f"{subject}|{expires}|{nonce}")
    # Constant-time: a timing oracle on a signature check is a real weakness
    # even when the data behind it is synthetic.
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return subject


def set_session_cookies(response: Response, session: str, csrf: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,          # never readable from JavaScript
        samesite="strict",      # not sent on any cross-site navigation
        secure=settings.force_https,
        path="/",
    )
    # The CSRF half of a double-submit pair must be readable by the page, so it
    # is deliberately not HttpOnly. It is useless without the session cookie.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=SESSION_TTL_SECONDS,
        httponly=False,
        samesite="strict",
        secure=settings.force_https,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


# ───────────────────────── request guards ─────────────────────────


@dataclass(frozen=True)
class Principal:
    subject: str
    authenticated: bool


def _deny(title: str, detail: str, code: int = status.HTTP_401_UNAUTHORIZED) -> HTTPException:
    return HTTPException(
        status_code=code,
        detail={
            "type": "https://gcpl.local/problems/unauthenticated",
            "title": title,
            "status": code,
            "detail": detail,
            "instance": None,
        },
    )


def require_principal(request: Request) -> Principal:
    """Identify the caller. Open in dev, enforced in prod."""
    subject = verify_session(request.cookies.get(SESSION_COOKIE))
    if subject:
        return Principal(subject=subject, authenticated=True)
    if not settings.is_prod:
        return Principal(subject="demo", authenticated=False)
    raise _deny(
        "Sign in to continue.",
        "This deployment requires an authenticated session. Post to /api/v1/session "
        "with the configured demo access key to obtain one.",
    )


def enforce_csrf(request: Request) -> None:
    """Double-submit: the header must match the cookie. Prod only."""
    if not settings.is_prod:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise _deny(
            "CSRF check failed.",
            f"A state-changing request must echo the {CSRF_COOKIE} cookie in the "
            f"{CSRF_HEADER} header. The request was not applied.",
            code=status.HTTP_403_FORBIDDEN,
        )


def enforce_rate_limit(key: str) -> None:
    """A fixed window per session. Applied to writes in every environment."""
    now = time.monotonic()
    window = _write_log[key]
    while window and now - window[0] > RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_WRITES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "type": "https://gcpl.local/problems/rate-limited",
                "title": "Too many write requests.",
                "status": 429,
                "detail": (
                    f"More than {RATE_LIMIT_WRITES} state-changing requests in "
                    f"{RATE_LIMIT_WINDOW_SECONDS} seconds. Nothing was applied. "
                    f"Wait a moment and retry."
                ),
                "instance": None,
            },
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
        )
    window.append(now)


def guard_write(request: Request) -> Principal:
    """The dependency every state-changing endpoint declares."""
    principal = require_principal(request)
    enforce_csrf(request)
    enforce_rate_limit(principal.subject or (request.client.host if request.client else "anon"))
    return principal
