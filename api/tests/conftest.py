"""Test fixtures.

Every test runs against a throwaway copy of the generated database, so a test
that tampers with a row (and one deliberately does) cannot corrupt the demo
data sitting in data/gcpl.db.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SOURCE_DB = REPO_ROOT / "data" / "gcpl.db"


@pytest.fixture(scope="session")
def source_db() -> Path:
    if not SOURCE_DB.exists():
        pytest.skip(
            "data/gcpl.db is missing. Run: python scripts/generate_data.py --seed 42"
        )
    return SOURCE_DB


@pytest.fixture
def db_path(source_db: Path, tmp_path: Path) -> Path:
    target = tmp_path / "gcpl.db"
    shutil.copy2(source_db, target)
    return target


@pytest.fixture
def engine(db_path: Path):
    from api.db import make_engine

    engine = make_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_path: Path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GCPL_DB_PATH", str(db_path))

    import api.config
    import api.db

    api.config.settings = api.config.Settings()
    monkeypatch.setattr(api.db, "settings", api.config.settings, raising=False)
    api.db.dispose()

    from api.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    api.db.dispose()


def headers(persona: str = "P2") -> dict[str, str]:
    return {"X-Persona": persona}
