"""Deterministic synthetic seed for GCPL Treasury Command (PRD section 12).

    python scripts/generate_data.py --seed 42

Determinism: the only source of randomness is random.Random(seed); there is no
call to datetime.now() anywhere in this file, every iteration order is fixed,
and the database is vacuumed before close. The same seed therefore produces a
byte-identical data/gcpl.db, which is what makes the demo reproducible.

The five invariants in PRD 12.3 are asserted before the file is written. The
script exits non-zero if any of them fails.
"""

from __future__ import annotations

import argparse
import os
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from api.config import normalise_database_url  # noqa: E402
from api.db import init_db, make_engine  # noqa: E402
from api.models import (  # noqa: E402
    Account,
    AuditEvent,
    Base,
    Balance,
    Bank,
    BankCountryCoverage,
    CounterpartyLimit,
    Country,
    Currency,
    DepositRate,
    Entity,
    Exposure,
    Facility,
    Forecast,
    ForecastLine,
    FxRate,
    Gate,
    KpiSnapshot,
    OnboardingItem,
    Persona,
    Pool,
    PoolMember,
    Proposal,
    ProposalCheck,
    Region,
    SodRule,
    Wave,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)
from api.services import audit as audit_service  # noqa: E402
from api.services import metrics, pooling, routing, scoring, sod  # noqa: E402
from scripts import seed_tables as T  # noqa: E402
from scripts import seed_workflows as W  # noqa: E402

AS_OF = T.AS_OF
START = AS_OF - timedelta(days=T.BALANCE_DAYS - 1)

# A fixed clock. Audit timestamps are derived from it, never from the wall clock,
# so two runs of the same seed produce identical hashes.
EPOCH = datetime(2026, 7, 20, 6, 0, 0, tzinfo=timezone.utc)


def stamp(minutes: int) -> str:
    return (EPOCH + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


# ───────────────────────── account estate ─────────────────────────

PURPOSE_PLAN: list[tuple[str, int]] = [
    ("operating", 3),
    ("collections", 3),
    ("payroll", 2),
    ("tax", 2),
    ("investment", 2),
    ("escrow", 1),
    ("debt_service", 1),
]

FEED_BY_CONNECTIVITY = {
    "swift_fileact": "camt053",
    "h2h": "mt940",
    "api": "api",
    "ebics": "camt053",
    "portal": "manual",
    "none": "none",
}

RESTRICTION_NOTES = {
    "tax": "Statutory withholding account. Balance is required by regulation to remain on deposit until the quarterly remittance.",
    "escrow": "Escrow mandated by the share purchase agreement. Ring-fenced until the indemnity period expires.",
    "payroll": "Payroll float held under a local statutory requirement to fund one cycle in advance.",
    "debt_service": "Debt service reserve required by the facility agreement. Not available for general corporate use.",
}

D_ROUTE_NOTE = (
    "Exchange control: outward remittance subject to central-bank approval and FX "
    "availability. Cash is declared as trapped and never swept."
)


def _banks_for_country(iso2: str) -> list[str]:
    return [b for b in sorted(T.BANK_COVERAGE) if iso2 in T.BANK_COVERAGE[b]]


def build_accounts(rng: random.Random) -> list[dict]:
    """81 accounts across 12 entities, at least 5 stale and at least 16 restricted."""
    accounts: list[dict] = []
    serial = 1000

    for entity in T.ENTITIES:
        iso2 = entity["country_iso2"]
        route = next(c["pooling_route"] for c in T.COUNTRIES if c["iso2"] == iso2)
        candidates = _banks_for_country(iso2)
        wanted = entity["accounts"]

        plan: list[str] = []
        for purpose, count in PURPOSE_PLAN:
            plan.extend([purpose] * count)
        plan = plan[:wanted] if wanted <= len(plan) else plan + ["operating"] * (wanted - len(plan))

        for index, purpose in enumerate(plan):
            bank_id = candidates[index % len(candidates)]
            bank = next(b for b in T.BANKS if b["id"] == bank_id)
            serial += 7
            opened = date(2015, 1, 1) + timedelta(days=rng.randrange(0, 3800))

            # Portal-only and unconnected banks are where staleness lives. That is
            # the honest cause: no file feed means someone keys it in by hand.
            if bank["connectivity"] == "none":
                feed_status = "offline"
            elif bank["connectivity"] == "portal" and index % 2 == 0:
                feed_status = "stale"
            else:
                feed_status = "live"

            if feed_status == "live":
                last_movement = AS_OF - timedelta(days=rng.randrange(0, 6))
            elif feed_status == "stale":
                last_movement = AS_OF - timedelta(days=rng.randrange(3, 40))
            else:
                last_movement = AS_OF - timedelta(days=rng.randrange(95, 420))

            restricted = purpose in RESTRICTION_NOTES or route == "D"
            if route == "D":
                note = D_ROUTE_NOTE
            else:
                note = RESTRICTION_NOTES.get(purpose)

            accounts.append(
                {
                    "id": f"ACC-{serial}",
                    "entity_id": entity["id"],
                    "bank_id": bank_id,
                    "iban_masked": f"****{serial % 10000:04d}",
                    "currency": entity["functional_ccy"],
                    "purpose": purpose,
                    "opened_on": opened,
                    "last_movement": last_movement,
                    "feed_type": FEED_BY_CONNECTIVITY[bank["connectivity"]],
                    "feed_status": feed_status,
                    "is_restricted": int(restricted),
                    "restriction_note": note,
                    "annual_cost_usd": float(
                        {"global": 9_600, "regional": 6_400, "domestic": 3_800}[bank["tier"]]
                        + rng.randrange(0, 2200)
                    ),
                }
            )
    return accounts


def allocate_balances(
    entity: dict, accounts: list[dict], rng: random.Random
) -> dict[str, float]:
    """Split the entity's stated cash across its accounts, honouring restricted_share.

    Restricted accounts receive exactly the restricted share in total, so
    INV-1 (total = available + restricted) holds by construction rather than
    by luck, and the restricted figure matches what the route model implies.
    """
    total = entity["cash_native"]
    restricted_total = total * entity["restricted_share"]
    available_total = total - restricted_total

    restricted = [a for a in accounts if a["is_restricted"]]
    unrestricted = [a for a in accounts if not a["is_restricted"]]

    def split(pool_total: float, members: list[dict]) -> dict[str, float]:
        if not members:
            return {}
        weights = [0.6 + rng.random() for _ in members]
        scale = pool_total / sum(weights)
        out = {m["id"]: w * scale for m, w in zip(members, weights, strict=True)}
        # Force the sum to land exactly on pool_total despite float drift.
        drift = pool_total - sum(out.values())
        out[members[0]["id"]] += drift
        return out

    allocation = split(restricted_total, restricted)
    allocation.update(split(available_total, unrestricted))
    return allocation


def build_balances(
    accounts: list[dict], rng: random.Random
) -> tuple[list[dict], dict[str, float]]:
    """90 days per account with plausible seasonality, landing on the stated total."""
    by_entity: dict[str, list[dict]] = {}
    for account in accounts:
        by_entity.setdefault(account["entity_id"], []).append(account)

    closing_on_as_of: dict[str, float] = {}
    rows: list[dict] = []

    for entity in T.ENTITIES:
        members = by_entity[entity["id"]]
        targets = allocate_balances(entity, members, rng)

        for account in members:
            final = targets[account["id"]]
            closing_on_as_of[account["id"]] = final

            # A gentle month-end bulge plus noise, walked backwards from the
            # known final balance so the last day is exactly the target.
            series: list[float] = []
            value = final
            for offset in range(T.BALANCE_DAYS):
                day = AS_OF - timedelta(days=offset)
                seasonal = 1.0 + 0.06 * (1 if day.day > 25 else -1)
                noise = 1.0 + (rng.random() - 0.5) * 0.09
                value = final * seasonal * noise if offset else final
                series.append(value)
            series.reverse()  # oldest first

            previous = series[0]
            for offset, closing in enumerate(series):
                day = START + timedelta(days=offset)
                rows.append(
                    {
                        "account_id": account["id"],
                        "as_of": day,
                        "opening_native": previous,
                        "closing_native": closing,
                        "value_dated_native": closing * (1.0 - rng.random() * 0.02),
                        "ingested_at": stamp(offset * 1440 + 30),
                    }
                )
                previous = closing

    return rows, closing_on_as_of


# ───────────────────────── funding ─────────────────────────

# Entities that carry drawn debt, and the rate they carry it at. Chosen so at
# least one borrowing rate sits well above a surplus entity's deposit rate,
# which is what guarantees the Cash Leak exists (PRD 12.1).
FACILITY_PLAN: list[dict] = [
    {"id": "FAC-001", "entity_id": "GCPL-US", "bank_id": "BNK-JPM", "kind": "rcf",
     "committed": 40_000_000.0, "drawn": 14_200_000.0, "benchmark": "SOFR",
     "spread_bps": 220, "all_in_rate": 0.0750, "maturity": date(2029, 3, 31),
     "covenant_note": "Net leverage not to exceed 3.0x, tested quarterly."},
    {"id": "FAC-002", "entity_id": "GCPL-DE", "bank_id": "BNK-DB", "kind": "term",
     "committed": 25_000_000.0, "drawn": 18_600_000.0, "benchmark": "EURIBOR",
     "spread_bps": 185, "all_in_rate": 0.0426, "maturity": date(2028, 9, 30),
     "covenant_note": "Interest cover not less than 4.0x."},
    {"id": "FAC-003", "entity_id": "GCPL-AU", "bank_id": "BNK-ANZ", "kind": "overdraft",
     "committed": 12_000_000.0, "drawn": 6_900_000.0, "benchmark": "SOFR",
     "spread_bps": 310, "all_in_rate": 0.0738, "maturity": date(2027, 6, 30),
     "covenant_note": None},
    {"id": "FAC-004", "entity_id": "GCPL-IN", "bank_id": "BNK-HDFC", "kind": "rcf",
     "committed": 3_500_000_000.0, "drawn": 1_180_000_000.0, "benchmark": "MCLR",
     "spread_bps": 95, "all_in_rate": 0.1010, "maturity": date(2028, 3, 31),
     "covenant_note": "Working capital facility. Drawing power reviewed monthly."},
    {"id": "FAC-005", "entity_id": "GCPL-PL", "bank_id": "BNK-SANT", "kind": "term",
     "committed": 9_000_000.0, "drawn": 7_400_000.0, "benchmark": "EURIBOR",
     "spread_bps": 265, "all_in_rate": 0.0506, "maturity": date(2030, 12, 31),
     "covenant_note": "Acquisition facility. Amortising from month 24."},
    {"id": "FAC-006", "entity_id": "GCPL-ID", "bank_id": "BNK-MANDIRI", "kind": "trade",
     "committed": 90_000_000_000.0, "drawn": 52_000_000_000.0, "benchmark": "SOFR",
     "spread_bps": 420, "all_in_rate": 0.0848, "maturity": date(2027, 3, 31),
     "covenant_note": "Onshore trade facility. Not refinanceable offshore."},
    {"id": "FAC-007", "entity_id": "GCPL-NG", "bank_id": "BNK-ZENITH", "kind": "overdraft",
     "committed": 14_000_000_000.0, "drawn": 9_100_000_000.0, "benchmark": "MCLR",
     "spread_bps": 600, "all_in_rate": 0.2450, "maturity": date(2027, 1, 31),
     "covenant_note": "Local-currency overdraft. Repricing monthly."},
    {"id": "FAC-008", "entity_id": "GCPL-GB", "bank_id": "BNK-BARC", "kind": "rcf",
     "committed": 30_000_000.0, "drawn": 0.0, "benchmark": "SONIA",
     "spread_bps": 150, "all_in_rate": 0.0605, "maturity": date(2029, 6, 30),
     "covenant_note": "Undrawn. Commitment fee 35bps."},
    {"id": "FAC-009", "entity_id": "GCPL-JP", "bank_id": "BNK-MUFG", "kind": "commercial_paper",
     "committed": 4_000_000_000.0, "drawn": 2_300_000_000.0, "benchmark": "SOFR",
     "spread_bps": 40, "all_in_rate": 0.0098, "maturity": date(2027, 2, 28),
     "covenant_note": "Rolling CP programme backed by the MUFG line."},
    {"id": "FAC-010", "entity_id": "GCPL-AE", "bank_id": "BNK-ENBD", "kind": "trade",
     "committed": 60_000_000.0, "drawn": 11_500_000.0, "benchmark": "SOFR",
     "spread_bps": 175, "all_in_rate": 0.0705, "maturity": date(2028, 6, 30),
     "covenant_note": None},
]

# Deposit rates. Low rates on large surplus balances against high borrowing
# rates elsewhere is precisely the Cash Leak the product exists to show.
DEPOSIT_RATES: dict[str, float] = {
    "GCPL-GB": 0.0045,
    "GCPL-NL": 0.0120,
    "GCPL-SG": 0.0205,
    "GCPL-AE": 0.0160,
    "GCPL-IN": 0.0325,
    "GCPL-JP": 0.0015,
    "GCPL-US": 0.0410,
    "GCPL-DE": 0.0115,
    "GCPL-AU": 0.0340,
    "GCPL-PL": 0.0180,
    "GCPL-ID": 0.0425,
    "GCPL-NG": 0.1150,
}


# ───────────────────────── writers ─────────────────────────


def write_reference(session: Session) -> None:
    for row in T.CURRENCIES:
        session.add(
            Currency(
                code=row["code"],
                name=row["name"],
                minor_units=row["minor_units"],
                symbol=row["symbol"],
            )
        )
    session.flush()
    for row in T.REGIONS:
        session.add(Region(**row))
    # Flushed before countries: country.region_id is a real foreign key and
    # SQLite runs here with foreign_keys = ON.
    session.flush()
    for row in T.COUNTRIES:
        session.add(Country(**row))
    session.flush()


def write_fx(session: Session) -> None:
    """A rate per currency per balance date, with a small deterministic drift."""
    for offset in range(T.BALANCE_DAYS):
        day = START + timedelta(days=offset)
        drift = 1.0 + (offset - T.BALANCE_DAYS / 2) * 0.00012
        for row in T.CURRENCIES:
            rate = row["usd"] if row["code"] == "USD" else row["usd"] * drift
            session.add(
                FxRate(
                    as_of=day,
                    base=row["code"],
                    quote="USD",
                    rate=rate if row["code"] != "USD" else 1.0,
                    source="BFIX",
                )
            )
    session.flush()


def write_entities(session: Session) -> None:
    for row in T.ENTITIES:
        session.add(
            Entity(
                id=row["id"],
                legal_name=row["legal_name"],
                short_name=row["short_name"],
                country_iso2=row["country_iso2"],
                region_id=row["region_id"],
                functional_ccy=row["functional_ccy"],
                erp_system=row["erp_system"],
                parent_id=row["parent_id"],
                ownership_pct=row["ownership_pct"],
                is_hq=row["is_hq"],
                acquired_on=row["acquired_on"],
                onboard_status=row["onboard_status"],
                pool_status=row["pool_status"],
                loc1_certified=row["loc1_certified"],
                operating_buffer_native=row["buffer_native"],
            )
        )
    session.flush()


def write_banks(session: Session) -> None:
    for row in T.BANKS:
        session.add(Bank(**row))
    session.flush()
    for bank_id in sorted(T.BANK_COVERAGE):
        served = set(T.BANK_COVERAGE[bank_id])
        for country in T.COUNTRIES:
            session.add(
                BankCountryCoverage(
                    bank_id=bank_id,
                    country_iso2=country["iso2"],
                    can_serve=int(country["iso2"] in served),
                )
            )
    session.flush()


def write_funding(session: Session, rng: random.Random) -> None:
    for plan in FACILITY_PLAN:
        session.add(
            Facility(
                id=plan["id"],
                entity_id=plan["entity_id"],
                bank_id=plan["bank_id"],
                kind=plan["kind"],
                currency=next(
                    e["functional_ccy"] for e in T.ENTITIES if e["id"] == plan["entity_id"]
                ),
                committed_native=plan["committed"],
                drawn_native=plan["drawn"],
                benchmark=plan["benchmark"],
                spread_bps=plan["spread_bps"],
                all_in_rate=plan["all_in_rate"],
                maturity=plan["maturity"],
                covenant_note=plan["covenant_note"],
            )
        )

    session.flush()
    for offset in range(T.BALANCE_DAYS):
        day = START + timedelta(days=offset)
        for entity in T.ENTITIES:
            base = DEPOSIT_RATES[entity["id"]]
            session.add(
                DepositRate(
                    entity_id=entity["id"],
                    currency=entity["functional_ccy"],
                    as_of=day,
                    rate=base,
                )
            )
    session.flush()


def write_forecasts(session: Session, rng: random.Random) -> None:
    """One 13-week cycle per entity, with actuals on the weeks already elapsed."""
    iso_year, iso_week, _ = AS_OF.isocalendar()
    categories = ("receipts", "payroll", "suppliers", "tax", "capex", "debt_service", "other")

    for entity in T.ENTITIES:
        forecast_id = f"FC-{entity['id']}-{iso_year}W{iso_week:02d}"
        scale = entity["cash_native"] / 13.0

        if entity["onboard_status"] == "not_onboarded":
            status, submitted_by = "draft", None
        elif entity["id"] == "GCPL-PL":
            status, submitted_by = "challenged", "P5"
        elif entity["onboard_status"] == "reporting_only":
            status, submitted_by = "submitted", "P5"
        else:
            status, submitted_by = "approved", "P5"

        session.add(
            Forecast(
                id=forecast_id,
                entity_id=entity["id"],
                cycle_week=iso_week,
                cycle_year=iso_year,
                horizon_weeks=13,
                submitted_at=stamp(1200) if submitted_by else None,
                submitted_by=submitted_by,
                reviewed_by="P4" if status in {"approved", "challenged"} else None,
                status=status,
            )
        )

        session.flush()
        for week in range(13):
            for category in categories:
                sign = 1.0 if category == "receipts" else -1.0
                weight = {
                    "receipts": 1.00,
                    "payroll": 0.22,
                    "suppliers": 0.41,
                    "tax": 0.09,
                    "capex": 0.07,
                    "debt_service": 0.05,
                    "other": 0.04,
                }[category]
                amount = sign * scale * weight * (0.85 + rng.random() * 0.3)
                # Weeks 0 to 3 have already happened, so they carry an actual.
                actual = (
                    amount * (0.88 + rng.random() * 0.24) if week < 4 and submitted_by else None
                )
                session.add(
                    ForecastLine(
                        forecast_id=forecast_id,
                        week_offset=week,
                        category=category,
                        amount_native=amount,
                        actual_native=actual,
                    )
                )
    session.flush()


def write_pools(session: Session) -> None:
    pools = [
        {
            "id": "POOL-APAC", "name": "APAC regional pool (Singapore header)",
            "kind": "physical", "header_entity_id": "GCPL-SG", "header_bank_id": "BNK-DBS",
            "currency": "SGD", "route": "B", "legal_cleared_by": "P10",
            "tax_cleared_by": "P10", "status": "live",
            "members": ["GCPL-SG", "GCPL-JP", "GCPL-AU"],
        },
        {
            "id": "POOL-EMEA", "name": "EMEA regional pool (Netherlands header)",
            "kind": "physical", "header_entity_id": "GCPL-NL", "header_bank_id": "BNK-ING",
            "currency": "EUR", "route": "B", "legal_cleared_by": "P10",
            "tax_cleared_by": "P10", "status": "live",
            "members": ["GCPL-NL", "GCPL-DE", "GCPL-GB"],
        },
        {
            "id": "POOL-IN", "name": "India domestic sweep (Route A)",
            "kind": "physical", "header_entity_id": "GCPL-IN", "header_bank_id": "BNK-HDFC",
            "currency": "INR", "route": "A", "legal_cleared_by": "P10",
            "tax_cleared_by": None, "status": "approved",
            "members": ["GCPL-IN"],
        },
        {
            "id": "POOL-GIFT", "name": "GIFT City GRCTC header (proposed)",
            "kind": "physical", "header_entity_id": "GCPL-IN", "header_bank_id": "BNK-SBI",
            "currency": "USD", "route": "C", "legal_cleared_by": None,
            "tax_cleared_by": None, "status": "legal_review",
            "members": [],
        },
        {
            "id": "POOL-ICL", "name": "Intercompany loan programme",
            "kind": "intercompany_loan", "header_entity_id": "GCPL-GB",
            "header_bank_id": "BNK-HSBC", "currency": "USD", "route": "B",
            "legal_cleared_by": "P10", "tax_cleared_by": "P10", "status": "approved",
            "members": ["GCPL-GB", "GCPL-US", "GCPL-AE"],
        },
    ]

    account_by_entity: dict[str, str] = {}
    for account_id, entity_id in session.execute(
        select(Account.id, Account.entity_id)
        .where(Account.purpose == "operating")
        .order_by(Account.id)
    ).all():
        account_by_entity.setdefault(entity_id, account_id)

    for row in pools:
        members = row.pop("members")
        session.add(Pool(**row))
        session.flush()
        for entity_id in members:
            account_id = account_by_entity.get(entity_id)
            if account_id is None:
                continue
            entity = next(e for e in T.ENTITIES if e["id"] == entity_id)
            session.add(
                PoolMember(
                    pool_id=row["id"],
                    entity_id=entity_id,
                    account_id=account_id,
                    sweep_target_native=entity["buffer_native"],
                )
            )
    session.flush()


def write_risk(session: Session, rng: random.Random) -> None:
    for bank in T.BANKS:
        base = {"global": 120_000_000.0, "regional": 60_000_000.0, "domestic": 25_000_000.0}[
            bank["tier"]
        ]
        for kind, share in (("cash", 1.0), ("facility", 0.7), ("derivative", 0.4)):
            limit = base * share
            session.add(
                CounterpartyLimit(
                    bank_id=bank["id"],
                    limit_kind=kind,
                    limit_usd=limit,
                    utilised_usd=limit * (0.18 + rng.random() * 0.55),
                )
            )

    kinds = ("fx_transaction", "fx_translation", "interest_rate", "commodity")
    serial = 0
    for entity in T.ENTITIES:
        for kind in kinds:
            serial += 1
            notional = entity["cash_native"] * 0.22 * (0.5 + rng.random())
            fx = next(c["usd"] for c in T.CURRENCIES if c["code"] == entity["functional_ccy"])
            notional_usd = notional * fx
            hedged = notional_usd * (0.35 + rng.random() * 0.55)
            session.add(
                Exposure(
                    id=f"EXP-{serial:03d}",
                    entity_id=entity["id"],
                    kind=kind,
                    currency_pair=(
                        f"{entity['functional_ccy']}/USD"
                        if kind.startswith("fx") and entity["functional_ccy"] != "USD"
                        else None
                    ),
                    notional_usd=notional_usd,
                    hedged_usd=min(hedged, notional_usd),
                    as_of=AS_OF,
                )
            )
    session.flush()


def write_governance(session: Session) -> None:
    for row in T.PERSONAS:
        session.add(Persona(**row))
    # Personas land before workflow nodes: workflow_node.required_persona is a
    # foreign key and the nodes below name personas by id.
    session.flush()
    for rule in T.SOD_RULES:
        session.add(
            SodRule(
                id=rule["id"],
                title=rule["title"],
                description=rule["description"],
                severity=rule["severity"],
                predicate=json.dumps(rule["predicate"], sort_keys=True),
            )
        )
    for workflow in W.WORKFLOWS:
        session.add(
            Workflow(
                id=workflow["id"],
                name=workflow["name"],
                description=workflow["description"],
                version=1,
                status="linted",
            )
        )
        nodes, edges = W.expand(workflow)
        for node in nodes:
            session.add(WorkflowNode(**node))
        # Nodes before edges: workflow_edge.from_node and .to_node are real
        # foreign keys into the rows just added.
        session.flush()
        for edge in edges:
            session.add(WorkflowEdge(**edge))
    session.flush()


def write_programme(session: Session, rng: random.Random) -> None:
    for row in T.WAVES:
        session.add(Wave(**row))
    for row in T.GATES:
        session.add(Gate(**row))

    session.flush()
    for entity in T.ENTITIES:
        for item_no, item, owner, due_day in T.ONBOARDING_ITEMS:
            if entity["onboard_status"] == "live":
                status = "done"
            elif entity["onboard_status"] == "onboarding":
                status = ("done", "done", "in_progress", "in_progress", "open", "open", "open")[
                    item_no - 1
                ]
            else:
                status = ("done", "done", "blocked", "in_progress", "open", "blocked", "open")[
                    item_no - 1
                ]
            session.add(
                OnboardingItem(
                    entity_id=entity["id"],
                    item_no=item_no,
                    item=item,
                    owner=owner,
                    due_day=due_day,
                    status=status,
                )
            )
    session.flush()


def write_kpi_targets(session: Session) -> None:
    """Targets only. Values are computed at request time, never read from here."""
    for code, target, unit in T.KPI_TARGETS:
        session.add(
            KpiSnapshot(kpi_code=code, as_of=AS_OF, value=0.0, target=target, unit=unit)
        )
    session.flush()


# ───────────────────────── proposals and audit ─────────────────────────

PROPOSAL_PLAN: list[dict] = [
    {"id": "PRP-0001", "kind": "intercompany_loan", "source": "GCPL-GB", "target": "GCPL-US",
     "amount_usd": 14_200_000.0, "tenor_days": 180, "rate": 0.0520,
     "basis": "6M Term SONIA + 65bps", "created_by": "P3", "approved_by": "P2",
     "settled_by": "P7", "status": "settled"},
    {"id": "PRP-0002", "kind": "intercompany_loan", "source": "GCPL-NL", "target": "GCPL-DE",
     "amount_usd": 18_600_000.0, "tenor_days": 90, "rate": 0.0486,
     "basis": "6M EURIBOR + 245bps", "created_by": "P3", "approved_by": "P4",
     "settled_by": None, "status": "authorised"},
    {"id": "PRP-0003", "kind": "sweep", "source": "GCPL-SG", "target": "GCPL-AU",
     "amount_usd": 6_900_000.0, "tenor_days": 30, "rate": 0.0533,
     "basis": "6M SORA + 224bps", "created_by": "P3", "approved_by": None,
     "settled_by": None, "status": "pending_auth"},
    {"id": "PRP-0004", "kind": "intercompany_loan", "source": "GCPL-IN", "target": "GCPL-AE",
     "amount_usd": 11_500_000.0, "tenor_days": 365, "rate": 0.0980,
     "basis": "SBI 1-yr MCLR + 325bps", "created_by": "P3", "approved_by": None,
     "settled_by": None, "status": "checks_failed"},
    {"id": "PRP-0005", "kind": "netting", "source": "GCPL-AE", "target": "GCPL-GB",
     "amount_usd": 3_400_000.0, "tenor_days": 1, "rate": 0.0000,
     "basis": "Settlement netting, no interest leg", "created_by": "P2",
     "approved_by": "P1", "settled_by": "P7", "status": "settled"},
    {"id": "PRP-0006", "kind": "fx_hedge", "source": "GCPL-JP", "target": "GCPL-SG",
     "amount_usd": 8_750_000.0, "tenor_days": 90, "rate": 0.0150,
     "basis": "Forward points, 3M JPY/USD", "created_by": "P3", "approved_by": None,
     "settled_by": None, "status": "rejected"},
]


def write_proposals(session: Session) -> None:
    for index, plan in enumerate(PROPOSAL_PLAN):
        route = metrics.pair_route(
            next(e["country_iso2"] for e in T.ENTITIES if e["id"] == plan["source"]),
            next(e["country_iso2"] for e in T.ENTITIES if e["id"] == plan["target"]),
        )
        created = stamp(2000 + index * 240)
        session.add(
            Proposal(
                id=plan["id"],
                kind=plan["kind"],
                source_entity_id=plan["source"],
                target_entity_id=plan["target"],
                amount_usd=plan["amount_usd"],
                tenor_days=plan["tenor_days"],
                route=route,
                interest_rate=plan["rate"],
                rate_basis=plan["basis"],
                created_by=plan["created_by"],
                created_at=created,
                approved_by=plan["approved_by"],
                approved_at=stamp(2060 + index * 240) if plan["approved_by"] else None,
                settled_by=plan["settled_by"],
                settled_at=stamp(2120 + index * 240) if plan["settled_by"] else None,
                status=plan["status"],
            )
        )
    session.flush()

    # Run the real engine over each proposal so the stored checks are the same
    # output a judge gets by re-running them, not a hand-written imitation.
    personas = {p.id: p for p in session.execute(select(Persona)).scalars()}
    for index, plan in enumerate(PROPOSAL_PLAN):
        draft = pooling.ProposalDraft(
            kind=plan["kind"],
            source_entity_id=plan["source"],
            target_entity_id=plan["target"],
            amount_usd=plan["amount_usd"],
            tenor_days=plan["tenor_days"],
            interest_rate=plan["rate"],
            rate_basis=plan["basis"],
        )
        results = pooling.evaluate(session, draft, personas[plan["created_by"]], AS_OF)
        for result in results:
            session.add(
                ProposalCheck(
                    proposal_id=plan["id"],
                    check_no=result.check_no,
                    code=result.code,
                    result=result.result,
                    detail=result.detail,
                    evaluated_at=stamp(2030 + index * 240),
                )
            )
    session.flush()


AUDIT_SCRIPT: list[tuple[str, str, str, str, str | None]] = [
    ("P9", "FEED_CONNECTED", "account",
     "camt.053 feed established and first file parsed.", None),
    ("P7", "BALANCE_INGESTED", "account",
     "Closing balance ingested and normalised against the ERP mapping.", None),
    ("P6", "FEED_STALE_FLAGGED", "account",
     "Feed exceeded the 24 h freshness threshold and was flagged to the owner.", None),
    ("P5", "FORECAST_SUBMITTED", "forecast",
     "13-week cycle submitted for regional review.", "Cycle deadline reached."),
    ("P4", "FORECAST_CHALLENGED", "forecast",
     "Receipts line challenged against the prior four weeks of actuals.",
     "Variance above the agreed tolerance."),
    ("P6", "LIMIT_SET", "bank",
     "Counterparty cash limit reviewed and set for the quarter.",
     "Quarterly counterparty limit review."),
    ("P10", "ROUTE_ASSESSED", "entity",
     "Route classification recorded with the governing citation.",
     "Pool eligibility assessment."),
    ("P2", "POOL_APPROVED", "pool",
     "Pool design approved for operation after legal and tax clearance.",
     "Legal and tax clearance on file."),
]


def write_audit(session: Session, rng: random.Random) -> None:
    """A valid hash chain from genesis, over 200 events."""
    personas = {p.id: p for p in session.execute(select(Persona)).scalars()}
    accounts = list(session.execute(select(Account.id).order_by(Account.id)).scalars())
    entities = [e["id"] for e in T.ENTITIES]
    banks = [b["id"] for b in T.BANKS]
    pools = ["POOL-APAC", "POOL-EMEA", "POOL-IN", "POOL-ICL"]
    iso_year, iso_week, _ = AS_OF.isocalendar()

    minute = 0
    for cycle in range(26):
        for actor_id, action, obj_kind, detail, justification in AUDIT_SCRIPT:
            minute += 17
            if obj_kind == "account":
                obj_id = accounts[(cycle * 3 + len(action)) % len(accounts)]
            elif obj_kind == "entity":
                obj_id = entities[cycle % len(entities)]
            elif obj_kind == "bank":
                obj_id = banks[(cycle * 2) % len(banks)]
            elif obj_kind == "pool":
                obj_id = pools[cycle % len(pools)]
            else:
                obj_id = f"FC-{entities[cycle % len(entities)]}-{iso_year}W{iso_week:02d}"
            audit_service.append(
                session,
                actor=personas[actor_id],
                action=action,
                obj_kind=obj_kind,
                obj_id=obj_id,
                detail=detail,
                justification=justification,
                ts=stamp(minute),
            )

    # The proposal lifecycle, chained after the operational events.
    for plan in PROPOSAL_PLAN:
        minute += 23
        audit_service.append(
            session,
            actor=personas[plan["created_by"]],
            action="PROPOSAL_CREATED",
            obj_kind="proposal",
            obj_id=plan["id"],
            detail=(
                f"{plan['kind']} of {plan['amount_usd']:,.0f} USD from {plan['source']} "
                f"to {plan['target']} at {plan['rate']:.2%} for {plan['tenor_days']} days."
            ),
            justification="Surplus and borrowing overlap identified in the daily position.",
            ts=stamp(minute),
        )
        if plan["approved_by"]:
            minute += 11
            audit_service.append(
                session,
                actor=personas[plan["approved_by"]],
                action="PROPOSAL_APPROVED",
                obj_kind="proposal",
                obj_id=plan["id"],
                detail=(
                    f"Approved by {plan['approved_by']}, distinct from creator "
                    f"{plan['created_by']} under LR1."
                ),
                justification="All nine checks cleared and the movement is within mandate.",
                ts=stamp(minute),
            )
        if plan["settled_by"]:
            minute += 9
            audit_service.append(
                session,
                actor=personas[plan["settled_by"]],
                action="PROPOSAL_SETTLED",
                obj_kind="proposal",
                obj_id=plan["id"],
                detail=(
                    f"Settled by {plan['settled_by']}, independent of creator "
                    f"{plan['created_by']} and approver {plan['approved_by']} under LR4."
                ),
                justification="Confirmation matched against the counterparty advice.",
                ts=stamp(minute),
            )
        if plan["status"] == "rejected":
            minute += 7
            audit_service.append(
                session,
                actor=personas["P2"],
                action="PROPOSAL_REJECTED",
                obj_kind="proposal",
                obj_id=plan["id"],
                detail="Rejected at authorisation and returned to the dealer.",
                justification="Hedge ratio already within policy; no incremental cover required.",
                ts=stamp(minute),
            )
    session.flush()


def lint_all_workflows(session: Session) -> int:
    """Run the real linter and persist what it finds, with a fixed timestamp."""
    total = 0
    for workflow_id in [w["id"] for w in W.WORKFLOWS]:
        violations = sod.lint_workflow(session, workflow_id)
        sod.persist(session, workflow_id, violations)
        total += len(violations)
    # persist() stamps with the wall clock; rewrite to the fixed epoch so the
    # generated file stays byte-identical across runs.
    session.execute(text("UPDATE sod_violation SET detected_at = :ts"), {"ts": stamp(9000)})
    session.flush()
    return total


def score_estate(session: Session) -> int:
    scores = scoring.score_accounts(session, None, AS_OF)
    return scoring.persist_scores(session, scores)


# ───────────────────────── invariants (PRD 12.3) ─────────────────────────


def assert_invariants(session: Session) -> list[str]:
    """Assert, do not hope. Returns the list of checks that passed."""
    passed: list[str] = []
    financials = metrics.entity_financials(session, AS_OF)

    for fin in financials.values():
        reconstructed = fin.available_local_native + fin.restricted_native
        assert abs(fin.total_cash_native - reconstructed) < 0.01, (
            f"INV-1 failed for {fin.entity_id}: total {fin.total_cash_native} is not "
            f"available {fin.available_local_native} + restricted {fin.restricted_native}"
        )
        assert fin.deployable_surplus_native <= fin.available_local_native + 0.01, (
            f"INV-1 failed for {fin.entity_id}: deployable surplus exceeds available cash"
        )
    passed.append("INV-1 total_cash = available_local + restricted, for every entity")

    for fin in financials.values():
        expected = fin.available_local_native - fin.deployable_surplus_native
        assert abs(fin.operating_buffer_native - expected) < 0.01, (
            f"INV-2 failed for {fin.entity_id}: buffer is not available_local - deployable"
        )
        assert fin.operating_buffer_native >= -0.01, (
            f"INV-2 failed for {fin.entity_id}: operating buffer is negative"
        )
    passed.append("INV-2 operating_buffer = available_local - deployable_surplus >= 0")

    leak = metrics.cash_leak(session, AS_OF)
    assert leak["pairs"], "dataset must contain at least one Cash Leak pair"
    assert leak["total_annualised_usd"] > 0, "Cash Leak must be a positive figure"
    passed.append(
        f"Cash Leak present: {len(leak['pairs'])} pairs totalling "
        f"{leak['total_annualised_usd']:,.0f} USD per year"
    )

    chain = audit_service.verify(session)
    assert chain.intact, f"generated audit chain must be intact (broken at {chain.broken_at})"
    passed.append(f"Audit chain intact across {chain.checked} events")

    # CASE rather than SUM(feed_status = 'live'): SQLite scores a comparison as
    # 1 or 0, Postgres returns a boolean and refuses to sum it. This line
    # computes INV-3, so the dialect-specific form would have taken the cash
    # visibility headline down with it.
    visibility = session.execute(
        text(
            "SELECT CAST(SUM(CASE WHEN feed_status = 'live' THEN 1 ELSE 0 END) AS FLOAT)"
            " / COUNT(*) FROM account"
        )
    ).scalar_one()
    assert 0.0 < visibility < 1.0, "cash visibility must be a computed fraction, not 0 or 1"
    passed.append(f"Cash visibility computed from feed status: {visibility:.1%}")

    return passed


# ───────────────────────── orchestration ─────────────────────────


def generate(target: Path | str, seed: int) -> dict:
    """Write the dataset to a SQLite file or to any SQLAlchemy URL.

    The same seed produces the same figures either way. Only a SQLite file is
    byte-identical between runs; a server-side database has its own physical
    layout, so determinism is asserted on the data rather than the bytes.
    """
    rng = random.Random(seed)
    is_file = isinstance(target, Path)

    if is_file:
        if target.exists():
            target.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = target.with_name(target.name + suffix)
            if sidecar.exists():
                sidecar.unlink()

    engine = make_engine(target)

    if not is_file:
        # No file to delete, so the previous dataset is dropped explicitly.
        # Re-seeding has to be repeatable: appending to a populated schema
        # would break the audit chain's genesis and every uniqueness rule.
        Base.metadata.drop_all(engine)

    init_db(engine)

    with Session(engine) as session:
        write_reference(session)
        write_fx(session)
        write_entities(session)
        write_banks(session)

        accounts = build_accounts(rng)
        for row in accounts:
            session.add(Account(**row))
        session.flush()

        balance_rows, _ = build_balances(accounts, rng)
        for row in balance_rows:
            session.add(Balance(**row))
        session.flush()

        write_funding(session, rng)
        write_forecasts(session, rng)
        write_pools(session)
        write_risk(session, rng)
        write_governance(session)
        write_programme(session, rng)
        write_kpi_targets(session)
        write_proposals(session)
        write_audit(session, rng)

        violations = lint_all_workflows(session)
        scored = score_estate(session)
        session.commit()

    with Session(engine) as verify_session:
        checks = assert_invariants(verify_session)
        leak = metrics.cash_leak(verify_session, AS_OF)
        counts = {
            "regions": len(T.REGIONS),
            "countries": len(T.COUNTRIES),
            "currencies": len(T.CURRENCIES),
            "entities": len(T.ENTITIES),
            "banks": len(T.BANKS),
            "accounts": len(accounts),
            "balances": len(balance_rows),
            "facilities": len(FACILITY_PLAN),
            "workflows": len(W.WORKFLOWS),
            "sod_violations": violations,
            "scored_accounts": scored,
            "proposals": len(PROPOSAL_PLAN),
            "audit_events": verify_session.execute(
                text("SELECT COUNT(*) FROM audit_event")
            ).scalar_one(),
            "cash_leak_usd": leak["total_annualised_usd"],
            "checks": checks,
        }

    if is_file:
        # VACUUM normalises page layout, so two runs of the same seed are
        # byte-identical. Neither pragma exists outside SQLite.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.exec_driver_sql("PRAGMA journal_mode = DELETE")
            conn.exec_driver_sql("VACUUM")
    engine.dispose()

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic GCPL dataset.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed. Same seed, same file.")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data" / "gcpl.db",
        help="SQLite output path. Defaults to data/gcpl.db inside the repository.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "Seed a server database instead of a SQLite file. Defaults to "
            "DATABASE_URL from the environment when that is set."
        ),
    )
    args = parser.parse_args(argv)

    # A URL wins over the file. Without this, seeding a deployment would
    # silently rewrite the local SQLite file and leave the server empty, and
    # the deployment would answer every request with a missing-table error.
    url = normalise_database_url(args.database_url or os.environ.get("DATABASE_URL"))
    target: Path | str = url or args.out

    try:
        counts = generate(target, args.seed)
    except AssertionError as failure:
        print(f"INVARIANT FAILED: {failure}", file=sys.stderr)
        return 1

    if url:
        # Never print the URL: it carries the password.
        shown = "the configured database"
    else:
        shown = args.out
        if args.out.is_absolute() and args.out.is_relative_to(REPO_ROOT):
            shown = args.out.relative_to(REPO_ROOT)

    print(f"Wrote {shown}")
    print(
        f"  {counts['regions']} regions, {counts['countries']} countries, "
        f"{counts['currencies']} currencies, {counts['entities']} entities"
    )
    print(
        f"  {counts['banks']} banks, {counts['accounts']} accounts, "
        f"{counts['balances']} balance rows over {T.BALANCE_DAYS} days"
    )
    print(
        f"  {counts['facilities']} facilities, {counts['proposals']} proposals, "
        f"{counts['workflows']} workflows, {counts['sod_violations']} SoD violations found"
    )
    print(
        f"  {counts['audit_events']} audit events, "
        f"{counts['scored_accounts']} accounts scored"
    )
    print(f"  Cash Leak: {counts['cash_leak_usd']:,.0f} USD annualised")
    print("Invariants:")
    for check in counts["checks"]:
        print(f"  OK  {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
