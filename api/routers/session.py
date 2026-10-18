"""Session endpoints.

The demo access key is read from the environment and never written into the
repository. In dev there is no key and no session is needed; in prod the key
must be set or the endpoint refuses to issue anything at all, which fails
closed rather than open.
"""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Request, Response, status
from fastapi import HTTPException
from pydantic import BaseModel, Field

from ..auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    clear_session_cookies,
    issue_session,
    set_session_cookies,
    verify_session,
)
from ..config import settings

router = APIRouter(tags=["session"])


class SignIn(BaseModel):
    access_key: str = Field(min_length=1, max_length=256)


class SessionOut(BaseModel):
    authenticated: bool
    subject: str | None
    environment: str
    csrf_cookie: str
    note: str


@router.get("/session", response_model=SessionOut, summary="Current session state")
def read_session(request: Request) -> SessionOut:
    subject = verify_session(request.cookies.get(SESSION_COOKIE))
    return SessionOut(
        authenticated=bool(subject),
        subject=subject,
        environment=settings.env,
        csrf_cookie=CSRF_COOKIE,
        note=(
            "This deployment requires an authenticated session for every write."
            if settings.is_prod
            else "Development mode: writes are open and persona switching is free. "
            "Capability rules (who may approve, who may settle) are enforced regardless."
        ),
    )


@router.post(
    "/session",
    response_model=SessionOut,
    summary="Exchange the demo access key for a signed session cookie",
)
def sign_in(body: SignIn, response: Response) -> SessionOut:
    expected = os.environ.get("GCPL_ACCESS_KEY")

    if not expected:
        if settings.is_prod:
            # Fail closed: a prod deployment with no key configured issues nothing.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "type": "https://gcpl.local/problems/not-configured",
                    "title": "Sign-in is not configured.",
                    "status": 503,
                    "detail": "GCPL_ACCESS_KEY is unset on this deployment.",
                    "instance": "/session",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://gcpl.local/problems/not-required",
                "title": "No session is required here.",
                "status": 400,
                "detail": "This is a development deployment. Writes are already open.",
                "instance": "/session",
            },
        )

    if not hmac.compare_digest(body.access_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://gcpl.local/problems/bad-credentials",
                "title": "That access key is not valid.",
                "status": 401,
                # Deliberately uninformative: never say which part was wrong.
                "detail": "Check the key and try again.",
                "instance": "/session",
            },
        )

    session, csrf = issue_session("demo-operator")
    set_session_cookies(response, session, csrf)
    return SessionOut(
        authenticated=True,
        subject="demo-operator",
        environment=settings.env,
        csrf_cookie=CSRF_COOKIE,
        note="Session issued. Echo the CSRF cookie in X-CSRF-Token on every write.",
    )


@router.post("/session/end", summary="Sign out and clear the session cookies")
def sign_out(response: Response) -> dict:
    clear_session_cookies(response)
    return {"authenticated": False}
