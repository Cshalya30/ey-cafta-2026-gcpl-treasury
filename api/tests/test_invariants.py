"""INV-1, INV-2 and INV-3 (PRD section 4.3).

These are the regression tests for the three number contradictions that broke
v1. They are cheap and they would have caught all of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from api.services import metrics

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_entity_balance_decomposition(session):
    """INV-1: total_cash = available_local + restricted, and surplus is a subset."""
    financials = metrics.entity_financials(session)
    assert financials, "the dataset must contain entities"

    for fin in financials.values():
        assert abs(
            fin.total_cash_native - (fin.available_local_native + fin.restricted_native)
        ) < 0.01, f"{fin.entity_id}: total is not available + restricted"
        assert fin.deployable_surplus_native <= fin.available_local_native + 0.01, (
            f"{fin.entity_id}: deployable surplus is not a subset of available cash"
        )


def test_operating_buffer_nonneg(session):
    """INV-2: buffer = available_local - deployable_surplus, never negative."""
    for fin in metrics.entity_financials(session).values():
        expected = fin.available_local_native - fin.deployable_surplus_native
        assert abs(fin.operating_buffer_native - expected) < 0.01
        assert fin.operating_buffer_native >= -0.01


def test_cash_visibility_single_source(session):
    """INV-3: visibility is computed from feed_status, nowhere else."""
    from sqlalchemy import func, select

    from api.models import Account

    total = session.execute(select(func.count()).select_from(Account)).scalar_one()
    live = session.execute(
        select(func.count()).select_from(Account).where(Account.feed_status == "live")
    ).scalar_one()

    kpi = next(k for k in metrics.kpis(session) if k.code == "cash_visibility")
    assert kpi.value == pytest.approx(live / total)
    assert kpi.source == f"{live} of {total} account feeds current"


# ───────────────────────── grep-based guards ─────────────────────────

SCANNED_ROOTS = ("api", "scripts", "web/src")
SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".html"}

# lib/format.ts is the one place numbers become strings, and the generator is
# the one place the synthetic dataset's figures are allowed to be literals.
EXEMPT = {
    "web/src/lib/format.ts",
    "scripts/seed_tables.py",
    "scripts/generate_data.py",
    "api/services/routing.py",  # published benchmark levels, with citations
}


SKIPPED_DIRS = {"node_modules", "__pycache__", "tests", "dist", ".vite"}


def _scanned_files() -> list[Path]:
    """Production source only.

    The test tree is excluded deliberately: these guards are regexes, and a
    file that defines the pattern will always match it. Excluding the tests
    keeps the guard honest about the code that actually ships.
    """
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
                continue
            if SKIPPED_DIRS & set(path.parts):
                continue
            if path.relative_to(REPO_ROOT).as_posix() in EXEMPT:
                continue
            files.append(path)
    return files


PERCENT_LITERAL = re.compile(r"[^\w.]\d{1,3}\.\d+\s*%")
CURRENCY_SYMBOL = re.compile(r"[£€₹¥]")
THOUSANDS_SEPARATED = re.compile(r"[^\w.]\d{1,3}(,\d{3})+(\.\d+)?")


def test_no_hardcoded_numbers():
    """The one test that matters most (PRD 8.12).

    v1 shipped four contradictory figures because none of them came from the
    data. Percentage literals, currency symbols and thousands separators belong
    in lib/format.ts and nowhere else.
    """
    offences: list[str] = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("#", "//", "*")):
                continue
            where = f"{path.relative_to(REPO_ROOT).as_posix()}:{number}"
            if PERCENT_LITERAL.search(line):
                offences.append(f"{where} percentage literal: {stripped[:90]}")
            if CURRENCY_SYMBOL.search(line):
                offences.append(f"{where} currency symbol: {stripped[:90]}")
            if THOUSANDS_SEPARATED.search(line):
                offences.append(f"{where} thousands separator: {stripped[:90]}")

    assert not offences, "Numbers must flow through lib/format.ts or the API:\n" + "\n".join(
        offences
    )


# Path-shaped only: a drive letter followed by a separator and a directory
# name, or a Unix home. A bare "e:\n" inside a string literal is not a path.
ABSOLUTE_PATH = re.compile(
    r"(?i)(\b[a-z]:[\\/]{1,2}(users|home|documents|program|windows|temp)\b"
    r"|/Users/[a-z]|/home/[a-z])"
)


def test_no_absolute_local_paths():
    """PRD 13 repo hygiene. v1 shipped another person's home directory."""
    offences: list[str] = []
    for path in _scanned_files() + [REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"]:
        if not path.exists():
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            if ABSOLUTE_PATH.search(line):
                offences.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{number} {line.strip()[:90]}"
                )
    assert not offences, "No committed file may carry an absolute local path:\n" + "\n".join(
        offences
    )


# Real listed issuers that must never appear attached to invented financials.
FORBIDDEN_ISSUERS = (
    "Godrej",
    "Hindustan Unilever",
    "Procter & Gamble",
    "Colgate-Palmolive",
    "Dabur",
    "Marico",
    "Nestle India",
    "ITC Limited",
)


def test_no_real_issuer_names(session):
    """PRD 12.2 and Appendix C defect 1.

    Bank names may be real. Issuer names may not: no invented financial is ever
    attached to a real listed company.
    """
    from sqlalchemy import select

    from api.models import Entity

    legal_names = list(session.execute(select(Entity.legal_name)).scalars())
    for name in legal_names:
        for forbidden in FORBIDDEN_ISSUERS:
            assert forbidden.lower() not in name.lower(), (
                f"Entity '{name}' carries a real listed issuer's name."
            )

    hq = [n for n in legal_names if "India HQ" in n]
    assert hq == ["Global Consumer Products Ltd (India HQ)"]


def test_no_full_account_numbers(session):
    """No account number longer than the last four digits reaches the database."""
    from sqlalchemy import select

    from api.models import Account

    for masked in session.execute(select(Account.iban_masked)).scalars():
        digits = [c for c in masked if c.isdigit()]
        assert len(digits) <= 4, f"'{masked}' exposes more than four digits"
