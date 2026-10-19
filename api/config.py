"""Runtime configuration.

Every value is read from the environment with a safe default. Nothing secret is
ever written into this file, and the application has no bank, payment or
market-data credentials by design: it holds synthetic data and moves no money.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def normalise_database_url(raw: str | None) -> str | None:
    """Return a SQLAlchemy URL, or None when nothing is configured.

    Hosted Postgres providers hand out `postgres://`, which SQLAlchemy has not
    accepted since 1.4, and a bare `postgresql://` would select psycopg2 rather
    than the psycopg 3 driver this project installs. Both are rewritten here so
    the value can be pasted from a dashboard unedited — the likeliest way for
    this to go wrong is a human retyping a connection string.
    """
    if not raw or not raw.strip():
        return None
    url = raw.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.environ.get("GCPL_ENV", "dev").lower())
    db_path: Path = field(
        default_factory=lambda: (
            Path(os.environ["GCPL_DB_PATH"]).expanduser()
            if os.environ.get("GCPL_DB_PATH")
            else REPO_ROOT / "data" / "gcpl.db"
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.environ.get("GCPL_CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
            if origin.strip()
        )
    )
    force_https: bool = field(default_factory=lambda: _flag("GCPL_FORCE_HTTPS"))
    # A per-boot random key in dev means no secret is ever written to disk or git.
    session_secret: str = field(
        default_factory=lambda: os.environ.get("GCPL_SESSION_SECRET")
        or secrets.token_urlsafe(48)
    )

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def docs_url(self) -> str | None:
        """OpenAPI docs are a development affordance. Closed in prod."""
        return None if self.is_prod else "/docs"

    def database_url(self) -> str:
        """The engine URL.

        DATABASE_URL wins when it is set, which is how the serverless
        deployment reaches Postgres. Without it the application keeps its
        SQLite file, so `python scripts/generate_data.py && uvicorn` still
        needs no database server and the two-command demo is unchanged.
        """
        return normalise_database_url(os.environ.get("DATABASE_URL")) or (
            f"sqlite:///{self.db_path.as_posix()}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url().startswith("sqlite")


settings = Settings()
