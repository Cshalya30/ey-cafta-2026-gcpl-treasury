"""The nine-constraint pooling engine (PRD section 9.2).

Evaluation never short-circuits: the user needs every failure at once, not the
first one. Every check states the arithmetic it used, because a check that says
only "passed" tells an approver nothing they can defend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Account, Bank, CounterpartyLimit, Entity, Forecast, ForecastLine, Persona
from . import metrics, routing

# A 30-day minimum liquidity coverage threshold must still hold after a movement.
POLICY_BUFFER_DAYS = 30

OKAY, WARN, ERR = "OKAY", "WARN", "ERR"


@dataclass(frozen=True)
class CheckResult:
    check_no: int
    code: str
    result: str
    detail: str

    @property
    def blocking(self) -> bool:
        return self.result == ERR


@dataclass(frozen=True)
class ProposalDraft:
    kind: str
    source_entity_id: str
    target_entity_id: str
    amount_usd: float
    tenor_days: int
    interest_rate: float
    rate_basis: str = ""
    rating_band: str = "BBB_band"


def _daily_burn_usd(session: Session, entity_id: str, fx_to_usd: float) -> float:
    """Average daily outflow across the entity's latest 13-week forecast."""
    latest = session.execute(
        select(Forecast.id, Forecast.horizon_weeks)
        .where(Forecast.entity_id == entity_id)
        .order_by(Forecast.cycle_year.desc(), Forecast.cycle_week.desc())
        .limit(1)
    ).first()
    if latest is None:
        return 0.0

    forecast_id, horizon_weeks = latest
    outflow = session.execute(
        select(func.sum(ForecastLine.amount_native)).where(
            ForecastLine.forecast_id == forecast_id,
            ForecastLine.category.in_(("payroll", "suppliers", "tax", "debt_service")),
        )
    ).scalar_one_or_none()

    weeks = max(int(horizon_weeks or 13), 1)
    weekly = abs(float(outflow or 0.0)) / weeks
    return (weekly / 7.0) * fx_to_usd


def evaluate(
    session: Session,
    draft: ProposalDraft,
    actor: Persona,
    as_of: date | None = None,
) -> list[CheckResult]:
    """Run all nine checks. Order is fixed; none of them short-circuits."""
    as_of = as_of or metrics.latest_as_of(session)
    financials = metrics.entity_financials(session, as_of)

    source = financials.get(draft.source_entity_id)
    target = financials.get(draft.target_entity_id)
    if source is None or target is None:
        missing = draft.source_entity_id if source is None else draft.target_entity_id
        return [
            CheckResult(n, code, ERR, f"Entity {missing} does not exist.")
            for n, code in enumerate(_CODES, start=1)
        ]

    source_entity = session.get(Entity, draft.source_entity_id)
    target_entity = session.get(Entity, draft.target_entity_id)
    fx = metrics.FxBook(session, as_of)
    usd_inr = fx.usd_per_unit_inverse("INR")

    results = [
        _check_route(source, target, source_entity, target_entity),
        _check_deployable(draft, source),
        _check_local_obligations(draft, source),
        _check_policy_buffer(session, draft, source),
        _check_facility(draft, target),
        _check_arms_length(draft, source_entity, usd_inr),
        _check_counterparty_limit(session, draft, target),
        _check_data_freshness(source, target),
        _check_sod(actor, draft),
    ]
    return results


_CODES = (
    "ROUTE_CLEARED",
    "DEPLOYABLE_LIMIT",
    "LOCAL_OBLIGATIONS",
    "POLICY_BUFFER",
    "FACILITY_CHECK",
    "ARMS_LENGTH",
    "COUNTERPARTY_LIMIT",
    "DATA_FRESHNESS",
    "SOD_CLEAR",
)


# ───────────────────────── 1. ROUTE_CLEARED ─────────────────────────


def _check_route(
    source: metrics.EntityFinancials,
    target: metrics.EntityFinancials,
    source_entity: Entity,
    target_entity: Entity,
) -> CheckResult:
    if source.route == "D" or target.route == "D":
        blocked = source.entity_id if source.route == "D" else target.entity_id
        return CheckResult(
            1,
            "ROUTE_CLEARED",
            ERR,
            f"{blocked} is Route D. Exchange control keeps this cash local; it is "
            f"declared as trapped and is never swept.",
        )

    route = metrics.pair_route(source_entity.country_iso2, target_entity.country_iso2)
    spec = routing.ROUTES[route]

    if route == "C":
        return CheckResult(
            1,
            "ROUTE_CLEARED",
            WARN,
            f"Route C ({source_entity.country_iso2} to {target_entity.country_iso2}): "
            f"{spec.binding_constraint} Tax and Legal Counsel must clear this route "
            f"before authorisation.",
        )

    return CheckResult(
        1,
        "ROUTE_CLEARED",
        OKAY,
        f"Route {route} ({spec.name}): {spec.mechanism}. "
        f"{source_entity.country_iso2} to {target_entity.country_iso2} permits this movement.",
    )


# ───────────────────────── 2. DEPLOYABLE_LIMIT ─────────────────────────


def _check_deployable(draft: ProposalDraft, source: metrics.EntityFinancials) -> CheckResult:
    available = source.deployable_surplus_usd
    if draft.amount_usd > available:
        return CheckResult(
            2,
            "DEPLOYABLE_LIMIT",
            ERR,
            f"Requested {draft.amount_usd:,.0f} USD exceeds {source.entity_id} "
            f"deployable surplus of {available:,.0f} USD by "
            f"{draft.amount_usd - available:,.0f} USD.",
        )
    return CheckResult(
        2,
        "DEPLOYABLE_LIMIT",
        OKAY,
        f"{draft.amount_usd:,.0f} USD of {available:,.0f} USD deployable surplus "
        f"({draft.amount_usd / available:.1%} utilised), leaving "
        f"{available - draft.amount_usd:,.0f} USD."
        if available
        else f"{source.entity_id} has no deployable surplus.",
    )


# ───────────────────────── 3. LOCAL_OBLIGATIONS ─────────────────────────


def _check_local_obligations(
    draft: ProposalDraft, source: metrics.EntityFinancials
) -> CheckResult:
    """LR12 made structural: the buffer is below the sweepable layer, not beside it."""
    buffer_usd = source.operating_buffer_usd
    after = source.available_local_usd - draft.amount_usd
    if after < buffer_usd - 0.01:
        return CheckResult(
            3,
            "LOCAL_OBLIGATIONS",
            ERR,
            f"Post-movement available cash {after:,.0f} USD falls below the protected "
            f"operating buffer of {buffer_usd:,.0f} USD. LR12: the local operating "
            f"buffer cannot be included in a sweep.",
        )
    return CheckResult(
        3,
        "LOCAL_OBLIGATIONS",
        OKAY,
        f"Operating buffer {buffer_usd:,.0f} USD is untouched. Available cash moves "
        f"{source.available_local_usd:,.0f} to {after:,.0f} USD, "
        f"{after - buffer_usd:,.0f} USD clear of the buffer.",
    )


# ───────────────────────── 4. POLICY_BUFFER ─────────────────────────


def _check_policy_buffer(
    session: Session, draft: ProposalDraft, source: metrics.EntityFinancials
) -> CheckResult:
    burn = _daily_burn_usd(session, source.entity_id, source.fx_to_usd)
    required = burn * POLICY_BUFFER_DAYS
    after = source.available_local_usd - draft.amount_usd

    if burn <= 0:
        return CheckResult(
            4,
            "POLICY_BUFFER",
            WARN,
            f"No forecast outflows recorded for {source.entity_id}, so the "
            f"{POLICY_BUFFER_DAYS}-day coverage threshold cannot be evaluated. "
            f"Submit the current cycle before relying on this check.",
        )

    days_covered = after / burn if burn else 0.0
    if after < required:
        return CheckResult(
            4,
            "POLICY_BUFFER",
            ERR,
            f"Post-movement cash {after:,.0f} USD covers {days_covered:.1f} days at "
            f"{burn:,.0f} USD/day, below the {POLICY_BUFFER_DAYS}-day policy minimum "
            f"of {required:,.0f} USD.",
        )
    return CheckResult(
        4,
        "POLICY_BUFFER",
        OKAY,
        f"Post-movement cash {after:,.0f} USD covers {days_covered:.1f} days at "
        f"{burn:,.0f} USD/day against a {POLICY_BUFFER_DAYS}-day minimum.",
    )


# ───────────────────────── 5. FACILITY_CHECK ─────────────────────────


def _check_facility(draft: ProposalDraft, target: metrics.EntityFinancials) -> CheckResult:
    drawn = target.drawn_usd
    if drawn <= 0:
        return CheckResult(
            5,
            "FACILITY_CHECK",
            ERR,
            f"{target.entity_id} has no drawn debt to repay. This movement would park "
            f"cash rather than avoid a drawdown, so it earns no spread for the group.",
        )
    repaid = min(draft.amount_usd, drawn)
    saved = repaid * (target.all_in_rate or 0.0)
    return CheckResult(
        5,
        "FACILITY_CHECK",
        OKAY,
        f"{target.entity_id} carries {drawn:,.0f} USD drawn at "
        f"{(target.all_in_rate or 0):.2%}. Repaying {repaid:,.0f} USD avoids "
        f"{saved:,.0f} USD of annual interest.",
    )


# ───────────────────────── 6. ARMS_LENGTH ─────────────────────────


def _check_arms_length(
    draft: ProposalDraft, source_entity: Entity, usd_inr: float
) -> CheckResult:
    harbour = routing.safe_harbour_floor(
        source_entity.functional_ccy,
        draft.rating_band,
        draft.amount_usd,
        usd_inr,
    )
    if draft.interest_rate < harbour.floor:
        shortfall_bps = (harbour.floor - draft.interest_rate) * 10_000
        return CheckResult(
            6,
            "ARMS_LENGTH",
            ERR,
            f"Proposed {draft.interest_rate:.2%} is {shortfall_bps:.0f}bps below the "
            f"safe-harbour floor of {harbour.floor:.2%} ({harbour.basis}). "
            f"{harbour.citation}",
        )
    headroom_bps = (draft.interest_rate - harbour.floor) * 10_000
    return CheckResult(
        6,
        "ARMS_LENGTH",
        OKAY,
        f"Proposed {draft.interest_rate:.2%} clears the safe-harbour floor of "
        f"{harbour.floor:.2%} by {headroom_bps:.0f}bps ({harbour.basis}). "
        f"{harbour.citation}",
    )


# ───────────────────────── 7. COUNTERPARTY_LIMIT ─────────────────────────


def _check_counterparty_limit(
    session: Session, draft: ProposalDraft, target: metrics.EntityFinancials
) -> CheckResult:
    row = session.execute(
        select(Bank.id, Bank.name, CounterpartyLimit.limit_usd, CounterpartyLimit.utilised_usd)
        .join(CounterpartyLimit, CounterpartyLimit.bank_id == Bank.id)
        .join(Account, Account.bank_id == Bank.id)
        .where(
            Account.entity_id == draft.target_entity_id,
            CounterpartyLimit.limit_kind == "cash",
        )
        .order_by(CounterpartyLimit.utilised_usd.desc())
        .limit(1)
    ).first()

    if row is None:
        return CheckResult(
            7,
            "COUNTERPARTY_LIMIT",
            WARN,
            f"No cash counterparty limit is recorded for {draft.target_entity_id}'s "
            f"banks. Risk and Control must set one before this concentration is approved.",
        )

    _, bank_name, limit_usd, utilised_usd = row
    after = float(utilised_usd) + draft.amount_usd
    utilisation = after / float(limit_usd) if limit_usd else 1.0

    if after > float(limit_usd):
        return CheckResult(
            7,
            "COUNTERPARTY_LIMIT",
            ERR,
            f"Post-movement exposure to {bank_name} of {after:,.0f} USD breaches the "
            f"{float(limit_usd):,.0f} USD cash limit by {after - float(limit_usd):,.0f} USD.",
        )
    if utilisation > 0.85:
        return CheckResult(
            7,
            "COUNTERPARTY_LIMIT",
            WARN,
            f"Post-movement exposure to {bank_name} reaches {utilisation:.1%} of the "
            f"{float(limit_usd):,.0f} USD cash limit. Approaching the ceiling.",
        )
    return CheckResult(
        7,
        "COUNTERPARTY_LIMIT",
        OKAY,
        f"Post-movement exposure to {bank_name} is {after:,.0f} USD, {utilisation:.1%} "
        f"of the {float(limit_usd):,.0f} USD cash limit.",
    )


# ───────────────────────── 8. DATA_FRESHNESS ─────────────────────────


def _check_data_freshness(
    source: metrics.EntityFinancials, target: metrics.EntityFinancials
) -> CheckResult:
    problems: list[str] = []
    for side, fin in (("source", source), ("target", target)):
        bad = fin.stale_accounts + fin.offline_accounts
        if bad:
            problems.append(
                f"{fin.entity_id} ({side}) has {fin.stale_accounts} stale and "
                f"{fin.offline_accounts} offline of {fin.account_count} accounts"
            )
    if problems:
        return CheckResult(
            8,
            "DATA_FRESHNESS",
            WARN,
            f"LR15: a feed over {metrics.STALE_AFTER_HOURS} h old is being used. "
            + "; ".join(problems)
            + ". The balance still renders, but the approver must see its age.",
        )
    return CheckResult(
        8,
        "DATA_FRESHNESS",
        OKAY,
        f"All {source.account_count + target.account_count} contributing account feeds "
        f"are under {metrics.STALE_AFTER_HOURS} h old.",
    )


# ───────────────────────── 9. SOD_CLEAR ─────────────────────────


def _check_sod(actor: Persona, draft: ProposalDraft) -> CheckResult:
    if not actor.can_initiate:
        return CheckResult(
            9,
            "SOD_CLEAR",
            ERR,
            f"{actor.display_name} ({actor.id}) holds no initiate capability. "
            f"LR9: Back Office cannot create a deal.",
        )
    if actor.scope_kind == "entity" and actor.scope_ref not in (
        draft.source_entity_id,
        draft.target_entity_id,
    ):
        return CheckResult(
            9,
            "SOD_CLEAR",
            ERR,
            f"LR10: {actor.display_name} is scoped to {actor.scope_ref} and cannot act "
            f"on a movement between {draft.source_entity_id} and {draft.target_entity_id}.",
        )
    return CheckResult(
        9,
        "SOD_CLEAR",
        OKAY,
        f"{actor.display_name} ({actor.id}) may initiate. Approval and settlement remain "
        f"with separate holders under LR1 and LR4.",
    )


def verdict(results: list[CheckResult]) -> str:
    """Resulting proposal status from a full evaluation."""
    if any(r.blocking for r in results):
        return "checks_failed"
    return "pending_auth"


def evaluated_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
