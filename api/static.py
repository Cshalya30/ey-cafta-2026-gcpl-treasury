"""Serving the built single-page app from the API process.

PRD section 6.1 puts a static mount in this application, and the reason is a
security property rather than a convenience. The client in
`web/src/lib/api.ts` calls `/api/v1` as a relative path and the CSRF guard is a
double-submit cookie pair, so the page and the API must share an origin. Split
across two hosts the app would need a cross-origin credentialled fetch and a
`SameSite=None` session cookie, which is a materially weaker posture for no
gain.

The mount is conditional. `web/dist` exists only after `npm run build`, so in
development and under pytest this module adds nothing and the API behaves
exactly as before.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .config import REPO_ROOT

DIST = REPO_ROOT / "web" / "dist"


class SpaStaticFiles(StaticFiles):
    """StaticFiles with a history fallback.

    The router in `web/src/app/routes.tsx` owns `/console`, `/brief`,
    `/cockpit/:entityId` and others. Those paths are not files on disk, so a
    plain StaticFiles 404s them and a judge who reloads the page or pastes a
    deep link gets nothing. Starlette's own `html=True` does not cover this: it
    serves `index.html` for a directory and `404.html` for a miss, never the
    app shell. So a miss is resolved to the shell and React Router decides what
    the path means, including rendering its own NotFound.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            # A missing hashed asset is a broken build, not a client route.
            # Saying so beats shipping HTML under a .js request, which the
            # browser would reject on nosniff anyway and more confusingly,
            # and beats caching that HTML for a year under the immutable
            # policy that /assets/ carries.
            #
            # StaticFiles.get_path runs the request through os.path.normpath,
            # so this arrives separated by backslashes on Windows and forward
            # slashes on the Linux image. Normalise before comparing.
            if path.replace("\\", "/").startswith("assets/"):
                raise
            return await super().get_response("index.html", scope)


def mount_spa(app: FastAPI) -> bool:
    """Mount the built app at the root. Returns whether anything was mounted.

    Called after the API routers are included, so every real endpoint is
    matched before the catch-all mount is consulted.
    """
    if not (DIST / "index.html").is_file():
        return False

    # Registered before the mount and after the routers: a real endpoint still
    # wins, and an unknown /api path stays a JSON problem document instead of
    # being answered with the HTML shell.
    # HEAD is listed explicitly: FastAPI does not derive it from GET the way
    # Starlette does, and without it an uptime monitor probing an unknown API
    # path falls through to the mount and gets the HTML shell with a 200.
    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "HEAD", "POST"],
        include_in_schema=False,
    )
    async def api_not_found(rest: str) -> Response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://gcpl.local/problems/no-such-endpoint",
                "title": "No such endpoint.",
                "status": 404,
                "detail": f"/api/{rest} is not part of this API.",
                "instance": f"/api/{rest}",
            },
        )

    app.mount("/", SpaStaticFiles(directory=DIST), name="spa")
    return True
