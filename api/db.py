"""Engine, session factory and the SQLite pragmas the schema depends on.

WAL is set once per database file; foreign_keys is per connection, so it is
applied on every checkout. Without the second pragma SQLite silently ignores
every REFERENCES clause in section 4.2.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base


def _connection_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


def make_engine(db_path: Path | None = None, *, echo: bool = False) -> Engine:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        echo=echo,
        future=True,
        # check_same_thread is a SQLite-driver guard, not a safety property of the
        # app; FastAPI hands each request its own session so the guard is noise.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _connection_pragmas)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode = WAL"))
    return engine


# The engine is built on first use, not on import. Importing api.db must not
# open (and therefore lock) the database file: the generator imports this module
# in order to rewrite that very file.
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = make_engine()
        _session_factory = sessionmaker(
            bind=_engine, autoflush=False, expire_on_commit=False
        )
    return _engine


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def dispose() -> None:
    """Release the file handle. Used by tests and by the generator."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_db(target: Engine | None = None) -> None:
    """Create every table from the ORM metadata. Idempotent."""
    Base.metadata.create_all(target or get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency. One session per request, always closed."""
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()
