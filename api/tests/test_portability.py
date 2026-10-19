"""The application runs on two dialects, and only one of them is testable here.

The suite runs on SQLite because it is fast and needs no server. The deployment
runs on Postgres because a serverless filesystem is ephemeral and per-instance,
which would fork the audit chain. That asymmetry is the risk these tests exist
to cover: a SQLite-only idiom passes every test and fails in front of a judge.

They compile rather than execute. No Postgres server is needed, and a type or
DDL construct the dialect cannot express fails here instead of at deploy time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from api.config import REPO_ROOT, normalise_database_url
from api.models import Base

DIALECTS = {"postgresql": postgresql.dialect(), "sqlite": sqlite.dialect()}


@pytest.mark.parametrize("dialect_name", sorted(DIALECTS))
def test_every_table_compiles_for_both_dialects(dialect_name):
    dialect = DIALECTS[dialect_name]
    for name, table in sorted(Base.metadata.tables.items()):
        try:
            CreateTable(table).compile(dialect=dialect)
            for index in table.indexes:
                CreateIndex(index).compile(dialect=dialect)
        except Exception as exc:  # pragma: no cover - the message is the point
            pytest.fail(f"{name} does not compile for {dialect_name}: {exc}")


def test_the_schema_declares_no_boolean_columns():
    """Integer flags keep the schema portable.

    SQLite scores `feed_status = 'live'` as 1 or 0 and lets an integer stand in
    a WHERE clause. Postgres returns a boolean, refuses to SUM it, and rejects
    a bare integer as a condition. Keeping flags as integers on both sides
    means an aggregate over one behaves the same way in either database.
    """
    offenders = [
        f"{table}.{column.name}"
        for table, t in Base.metadata.tables.items()
        for column in t.columns
        if column.type.__class__.__name__ == "Boolean"
    ]
    assert not offenders, (
        "Boolean columns differ between the two dialects in aggregates and "
        "conditions: " + ", ".join(offenders)
    )


def test_no_source_file_sums_a_comparison():
    """`SUM(x = 'y')` is valid SQLite and an error in Postgres.

    This is not hypothetical: the generator computed INV-3, the cash visibility
    headline, exactly that way until the Postgres migration.
    """
    pattern = re.compile(r"SUM\s*\(\s*[A-Za-z_.]+\s*=", re.IGNORECASE)
    offenders = []
    for root in ("api", "scripts"):
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                # A comment may legitimately quote the broken form in order to
                # explain why it is broken, as the generator's does.
                if line.strip().startswith("#"):
                    continue
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{number}")
    assert not offenders, (
        "Use SUM(CASE WHEN … THEN 1 ELSE 0 END), which both dialects accept:\n"
        + "\n".join(offenders)
    )


def test_the_visibility_query_compiles_for_both_dialects():
    query = text(
        "SELECT CAST(SUM(CASE WHEN feed_status = 'live' THEN 1 ELSE 0 END) AS FLOAT)"
        " / COUNT(*) FROM account"
    )
    for dialect in DIALECTS.values():
        query.compile(dialect=dialect)


# ───────────────────────── configuration ─────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("  postgres://u:p@h/db  ", "postgresql+psycopg://u:p@h/db"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_provider_connection_strings_are_normalised(raw, expected):
    """A string pasted from a dashboard must work unedited.

    `postgres://` has not been a valid SQLAlchemy URL since 1.4, and a bare
    `postgresql://` selects psycopg2, which this project does not install.
    """
    assert normalise_database_url(raw) == expected


def test_database_url_selects_the_dialect(monkeypatch):
    from api.config import Settings

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().is_sqlite

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    configured = Settings()
    assert not configured.is_sqlite
    assert configured.database_url().startswith("postgresql+psycopg://")


def test_the_two_dependency_lists_agree():
    """pyproject.toml drives the Vercel build; requirements.txt drives Docker.

    A dependency added to one and not the other fails on whichever platform was
    not tested, which is the platform nobody looks at until it matters.
    """
    requirements = {
        line.strip()
        for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    # tomllib, not a split: "uvicorn[standard]>=0.30" contains a bracket, and
    # splitting on it truncated the list to its first entry.
    import tomllib

    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = set(pyproject["project"]["dependencies"])

    assert declared == requirements, (
        "requirements.txt and pyproject.toml disagree.\n"
        f"  only in pyproject.toml: {sorted(declared - requirements)}\n"
        f"  only in requirements.txt: {sorted(requirements - declared)}"
    )


# ───────────────────────── seeding a server database ─────────────────────────


def test_the_seed_command_targets_the_url_not_the_file(monkeypatch, tmp_path):
    """The documented command must reach Postgres.

    It did not. `--out` is always a Path and main() never read DATABASE_URL, so
    `DATABASE_URL=… python scripts/generate_data.py` rewrote the local SQLite
    file and left the server empty — and the deployment then answered every
    request with a missing-table error.
    """
    import scripts.generate_data as generator

    seen: dict[str, object] = {}

    def fake_generate(target, seed):
        seen["target"] = target
        seen["seed"] = seed
        return {
            "regions": 0, "countries": 0, "currencies": 0, "entities": 0,
            "banks": 0, "accounts": 0, "balances": 0, "facilities": 0,
            "proposals": 0, "workflows": 0, "sod_violations": 0,
            "audit_events": 0, "scored_accounts": 0, "cash_leak_usd": 0.0,
            "checks": [],
        }

    monkeypatch.setattr(generator, "generate", fake_generate)

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    assert generator.main([]) == 0
    assert seen["target"] == "postgresql+psycopg://u:p@h/db"

    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "x.db"
    assert generator.main(["--out", str(out)]) == 0
    assert seen["target"] == out

    # An explicit flag beats the environment.
    monkeypatch.setenv("DATABASE_URL", "postgres://env/db")
    assert generator.main(["--database-url", "postgres://flag/db"]) == 0
    assert seen["target"] == "postgresql+psycopg://flag/db"


def test_the_seed_command_never_prints_the_connection_string(monkeypatch, capsys):
    """A URL carries the password, and this output gets pasted into chats."""
    import scripts.generate_data as generator

    monkeypatch.setattr(
        generator,
        "generate",
        lambda target, seed: {
            "regions": 0, "countries": 0, "currencies": 0, "entities": 0,
            "banks": 0, "accounts": 0, "balances": 0, "facilities": 0,
            "proposals": 0, "workflows": 0, "sod_violations": 0,
            "audit_events": 0, "scored_accounts": 0, "cash_leak_usd": 0.0,
            "checks": [],
        },
    )
    monkeypatch.setenv("DATABASE_URL", "postgres://user:hunter2@host/db")
    generator.main([])
    printed = capsys.readouterr().out
    assert "hunter2" not in printed
    assert "host" not in printed


# ───────────────────────── concurrent writers ─────────────────────────


def test_the_audit_append_serialises_writers(session):
    """Read-then-insert forks the chain unless appends are serialised.

    On SQLite the lock is a no-op because the database has one writer. The
    assertion here is that the call is present and harmless, so that the
    Postgres branch cannot be removed without a test noticing.
    """
    import inspect

    from api.db import serialise_writes
    from api.services import audit

    assert "serialise_writes" in inspect.getsource(audit.append)
    serialise_writes(session)  # must not raise on SQLite

    body = inspect.getsource(serialise_writes)
    assert "pg_advisory_xact_lock" in body
    assert "postgresql" in body


def test_proposal_ids_are_allocated_under_the_same_lock():
    """Two creates reading the same count collide on the primary key."""
    import inspect

    from api.routers import pooling

    source = inspect.getsource(pooling)
    allocation = source.split("proposal_id = f\"PRP-", 1)[0]
    assert "serialise_writes(scope.session)" in allocation[-600:]


# ───────────────────────── test isolation ─────────────────────────


def test_the_suite_cannot_reach_a_configured_server_database():
    """Seeding a deployment means exporting DATABASE_URL in a shell.

    Running pytest in that shell must not send tests that tamper with
    audit_event and update a deposit rate at the live demo.
    """
    import os

    assert "DATABASE_URL" not in os.environ, (
        "an autouse fixture in conftest.py should have removed it"
    )


# ───────────────────────── deployment configuration ─────────────────────────


def test_the_deployment_declares_one_service_serving_everything():
    """Two services would put the app on the CDN, and the CDN skips middleware.

    The two content security policies, the security headers and the HTTPS
    redirect all live in middleware. A frontend served directly from the CDN
    bypasses the function, so those responses would carry none of them, and the
    tests asserting they are present would keep passing while the deployment
    shipped without them.
    """
    import json

    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = config["services"]
    assert len(services) == 1, (
        "a second service would be served from the CDN, without middleware: "
        + ", ".join(sorted(services))
    )

    name, service = next(iter(services.items()))
    assert service["root"] == "."
    assert any(
        rule["source"] == "/(.*)" and rule["destination"] == {"service": name}
        for rule in config["rewrites"]
    ), "without a catch-all rewrite the service receives no public traffic at all"


def test_the_entrypoint_agrees_across_both_files():
    """vercel.json and pyproject.toml both name it; they must not drift."""
    import json
    import tomllib

    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    declared = config["services"]["app"]["entrypoint"]

    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert declared == pyproject["tool"]["vercel"]["entrypoint"]

    module, _, variable = declared.partition(":")
    imported = __import__(module, fromlist=[variable])
    from fastapi import FastAPI

    assert isinstance(getattr(imported, variable), FastAPI), (
        f"{declared} must resolve to the FastAPI instance Vercel loads"
    )


def test_the_function_region_is_pinned():
    """Co-location with the database is worth more than anything else here.

    Vercel defaults functions to iad1. With the database in Singapore, every
    query crossed the Pacific and the endpoints that issue several of them took
    seconds. The symptom was invisible to /health, which touches no database,
    so a smoke test would have reported the deployment healthy.
    """
    import json

    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    regions = config.get("regions")
    assert regions, (
        "Without this the function returns to iad1 and every database round "
        "trip costs roughly 220ms."
    )
    assert len(regions) == 1, "the Hobby plan allows exactly one region"


def test_the_deployment_config_carries_no_keys_outside_the_schema():
    """JSON has no comments, and Vercel rejects properties it does not define.

    A "comment" array was added here to explain the region choice. The file
    stopped being applied, the function silently stayed in the default region,
    and the only symptom was that database-backed endpoints were slow — while
    the build succeeded and /health answered in 0.3s. Explanations belong in
    docs/decisions, not in a config file that is validated against a schema.
    """
    import json

    config = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))

    allowed_top = {
        "$schema", "regions", "services", "rewrites", "redirects", "headers",
        "cleanUrls", "trailingSlash", "routes", "crons", "daemons", "git", "public",
    }
    assert not set(config) - allowed_top, (
        "unknown top-level keys: " + ", ".join(sorted(set(config) - allowed_top))
    )

    allowed_service = {
        "root", "framework", "runtime", "entrypoint", "command", "installCommand",
        "buildCommand", "devCommand", "ignoreCommand", "outputDirectory", "bindings",
        "functions", "headers", "redirects", "rewrites", "routes", "cleanUrls",
        "trailingSlash",
    }
    for name, service in config["services"].items():
        unknown = set(service) - allowed_service
        assert not unknown, f"service {name!r} has unknown keys: {sorted(unknown)}"


def test_derived_figures_are_computed_once_per_request(session):
    """kpis() computed entity_financials, then cash_leak() computed it again.

    Roughly eight queries, twice, for one response. In process that is
    invisible; against a database over a network it is half the latency of the
    slowest endpoint.
    """
    from api.services import metrics

    calls = {"n": 0}
    original = metrics._entity_financials

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    metrics._entity_financials = counting
    try:
        metrics.kpis(session)
    finally:
        metrics._entity_financials = original

    assert calls["n"] == 1, (
        f"entity_financials ran {calls['n']} times for one set of KPIs"
    )


def test_a_write_invalidates_the_cached_figures(session):
    """A cache that outlived a write would serve figures that contradict it."""
    from api.models import Account
    from api.services import metrics

    first = metrics.entity_financials(session)
    assert session.info.get(metrics._CACHE_KEY), "nothing was cached"

    account = session.execute(select(Account).limit(1)).scalar_one()
    account.feed_status = "stale" if account.feed_status == "live" else "live"
    session.flush()

    assert not session.info.get(metrics._CACHE_KEY), (
        "the flush must have dropped the derived figures"
    )
    session.rollback()
    assert first is not None
