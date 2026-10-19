"""Engine, session factory and the SQLite pragmas the schema depends on.

WAL is set once per database file; foreign_keys is per connection, so it is
applied on every checkout. Without the second pragma SQLite silently ignores
every REFERENCES clause in section 4.2.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base


def _connection_pragmas(dbapi_connection, _record) -> None:
    """SQLite only. Postgres enforces foreign keys without being asked."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.close()


def make_engine(
    target: Path | str | None = None, *, echo: bool = False
) -> Engine:
    """Build an engine for a SQLite path or any SQLAlchemy URL.

    Both dialects are real deployments of this application: SQLite for the
    local two-command demo and the test suite, Postgres for the serverless
    deployment, where the filesystem is ephemeral and requests fan out across
    instances that must all see the same audit chain. The ORM is identical for
    both; only the connection handling below differs.
    """
    if isinstance(target, str):
        url = target
    elif isinstance(target, Path):
        url = f"sqlite:///{target.as_posix()}"
    else:
        url = settings.database_url()

    if url.startswith("sqlite"):
        path = Path(url.replace("sqlite:///", "", 1))
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url,
            echo=echo,
            future=True,
            # check_same_thread is a SQLite-driver guard, not a safety property
            # of the app; FastAPI hands each request its own session so the
            # guard is noise.
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _connection_pragmas)
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode = WAL"))
        return engine

    # Postgres, behind a connection pooler, reached from short-lived serverless
    # instances. NullPool is correct here rather than pessimistic: a pool held
    # in an instance that may be frozen between requests hands back connections
    # the server has already dropped, and the pooler is doing the pooling.
    # pool_pre_ping covers the same hazard for any connection that is reused.
    return create_engine(
        url,
        echo=echo,
        future=True,
        poolclass=NullPool,
        pool_pre_ping=True,
        # psycopg 3 starts preparing a statement after it has been executed a
        # few times. A transaction-mode pooler hands the next execution to a
        # different backend session, where that prepared statement does not
        # exist, and the query fails. Hosted Postgres is normally reached
        # through exactly such a pooler.
        connect_args={"prepare_threshold": None},
    )


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


# A single advisory lock key for this application. Arbitrary but fixed; the
# value spells "gCPL" and only has to differ from other locks on the same
# database.
WRITE_LOCK_KEY = 0x6743504C


def serialise_writes(session: Session) -> None:
    """Serialise the read-then-insert sections against concurrent writers.

    `audit.append` reads the chain tail and inserts a row linked to it, and the
    proposal router reads a count and inserts an id derived from it. Both are
    read-then-insert. Two transactions at READ COMMITTED read the same value
    and both act on it: the chain forks, and `/audit/verify` then correctly
    reports a break — in the product whose argument is that the chain is
    verifiable.

    SQLite's single-writer lock hid this, which is why it has never been seen.
    Postgres with instances in parallel will not hide it.

    The lock is transaction-scoped and released on commit or rollback. It is a
    no-op on SQLite, which already serialises writers.
    """
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK_KEY}
        )
