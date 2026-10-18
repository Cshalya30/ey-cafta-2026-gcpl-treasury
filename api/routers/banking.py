"""Accounts, the four-test scorer, banks, the coverage matrix, balances and facilities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from ..models import (
    Account,
    Balance,
    Bank,
    BankCountryCoverage,
    CounterpartyLimit,
    Country,
    Entity,
    Facility,
)
from ..repositories.scope import Scope, current_scope
from ..schemas.treasury import (
    AccountOut,
    AccountScoreOut,
    BalanceOut,
    BankOut,
    CoverageMatrixOut,
    FacilityOut,
    ScoreRequest,
    ScoreResponse,
)
from ..services import audit as audit_service
from ..services import metrics, scoring
from .helpers import money_native
from ..auth import Principal, guard_write

router = APIRouter(tags=["banking"])

SCORER_METHOD = (
    "T1 panel coverage, T2 unique purpose, T3 activity within 90 days, T4 legal "
    "necessity. Each scores 1 or 0. Four keeps the account, two or three migrates "
    "it, zero or one closes it. T2 is evaluated across the entity's whole estate, "
    "not the filtered subset, so a filter never changes a score."
)


@router.get("/accounts", response_model=list[AccountOut], summary="The account estate")
def list_accounts(
    scope: Scope = Depends(current_scope),
    entity: str | None = Query(default=None, max_length=32),
    bank: str | None = Query(default=None, max_length=32),
    feed_status: str | None = Query(default=None, max_length=16),
    disposition: str | None = Query(default=None, max_length=16),
) -> list[AccountOut]:
    if entity:
        scope.require(entity)

    query = (
        select(Account, Bank.name)
        .join(Bank, Bank.id == Account.bank_id)
        .where(Account.entity_id.in_(scope.entity_ids))
        .order_by(Account.id)
    )
    if entity:
        query = query.where(Account.entity_id == entity)
    if bank:
        query = query.where(Account.bank_id == bank)
    if feed_status:
        query = query.where(Account.feed_status == feed_status)
    if disposition:
        query = query.where(Account.disposition == disposition)

    balances = dict(
        scope.session.execute(
            select(Balance.account_id, Balance.closing_native).where(
                Balance.as_of == scope.as_of
            )
        ).all()
    )
    fx = metrics.FxBook(scope.session, scope.as_of)

    out: list[AccountOut] = []
    for account, bank_name in scope.session.execute(query).all():
        scores = [
            account.score_panel,
            account.score_unique,
            account.score_active,
            account.score_legal,
        ]
        balance = balances.get(account.id)
        out.append(
            AccountOut(
                id=account.id,
                entity_id=account.entity_id,
                bank_id=account.bank_id,
                bank_name=bank_name,
                iban_masked=account.iban_masked,
                currency=account.currency,
                purpose=account.purpose,
                opened_on=account.opened_on,
                last_movement=account.last_movement,
                feed_type=account.feed_type,
                feed_status=account.feed_status,
                is_restricted=bool(account.is_restricted),
                restriction_note=account.restriction_note,
                annual_cost_usd=round(account.annual_cost_usd, 2),
                balance=(
                    money_native(balance, account.currency, fx.rate(account.currency))
                    if balance is not None and scope.sees_amounts
                    else None
                ),
                score_panel=account.score_panel,
                score_unique=account.score_unique,
                score_active=account.score_active,
                score_legal=account.score_legal,
                score_total=sum(s for s in scores if s is not None) if all(
                    s is not None for s in scores
                ) else None,
                disposition=account.disposition,
            )
        )
    return out


@router.post(
    "/accounts/score",
    response_model=ScoreResponse,
    summary="Run the four-test scorer over a filter set",
)
def score(request: ScoreRequest, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),) -> ScoreResponse:
    """Available to the Group Treasurer and the Risk and Control Analyst only."""
    scope.require_persona_in({"P2", "P6"}, "run the account rationalisation scorer")

    if request.entity_id:
        scope.require(request.entity_id)

    query = select(Account.id).where(Account.entity_id.in_(scope.entity_ids))
    if request.entity_id:
        query = query.where(Account.entity_id == request.entity_id)
    if request.bank_id:
        query = query.where(Account.bank_id == request.bank_id)
    if request.feed_status:
        query = query.where(Account.feed_status == request.feed_status)

    account_ids = list(scope.session.execute(query.order_by(Account.id)).scalars())
    results = scoring.score_accounts(scope.session, account_ids, scope.as_of)

    persisted = 0
    if request.persist:
        persisted = scoring.persist_scores(scope.session, results)
        audit_service.append(
            scope.session,
            actor=scope.persona,
            action="ESTATE_SCORED",
            obj_kind="account",
            obj_id=request.entity_id or "ALL",
            detail=f"Four-test scorer run over {len(results)} accounts.",
            justification="Bank rationalisation review.",
        )
        scope.session.commit()

    return ScoreResponse(
        as_of=scope.as_of.isoformat(),
        scored=len(results),
        persisted=persisted,
        method=SCORER_METHOD,
        results=[
            AccountScoreOut(
                account_id=r.account_id,
                score_panel=r.score_panel,
                score_unique=r.score_unique,
                score_active=r.score_active,
                score_legal=r.score_legal,
                score_total=r.total,
                disposition=r.disposition,
                reasons=r.reasons,
            )
            for r in results
        ],
    )


@router.get("/banks", response_model=list[BankOut], summary="The bank panel")
def list_banks(scope: Scope = Depends(current_scope)) -> list[BankOut]:
    counts = dict(
        scope.session.execute(
            select(Account.bank_id, func.count())
            .where(Account.entity_id.in_(scope.entity_ids))
            .group_by(Account.bank_id)
        ).all()
    )
    limits = {
        bank_id: (limit, used)
        for bank_id, limit, used in scope.session.execute(
            select(
                CounterpartyLimit.bank_id,
                CounterpartyLimit.limit_usd,
                CounterpartyLimit.utilised_usd,
            ).where(CounterpartyLimit.limit_kind == "cash")
        ).all()
    }
    coverage: dict[str, list[str]] = {}
    for bank_id, iso2 in scope.session.execute(
        select(BankCountryCoverage.bank_id, BankCountryCoverage.country_iso2)
        .where(BankCountryCoverage.can_serve == 1)
        .order_by(BankCountryCoverage.bank_id, BankCountryCoverage.country_iso2)
    ).all():
        coverage.setdefault(bank_id, []).append(iso2)

    out: list[BankOut] = []
    for bank in scope.session.execute(select(Bank).order_by(Bank.id)).scalars():
        limit = limits.get(bank.id)
        out.append(
            BankOut(
                id=bank.id,
                name=bank.name,
                tier=bank.tier,
                swift_bic=bank.swift_bic,
                connectivity=bank.connectivity,
                panel_status=bank.panel_status,
                account_count=int(counts.get(bank.id, 0)),
                countries_served=coverage.get(bank.id, []),
                limit_usd=round(limit[0], 2) if limit and scope.sees_amounts else None,
                utilised_usd=round(limit[1], 2) if limit and scope.sees_amounts else None,
            )
        )
    return out


@router.get(
    "/banks/coverage-matrix",
    response_model=CoverageMatrixOut,
    summary="Country by bank grid for rationalisation",
)
def coverage_matrix(scope: Scope = Depends(current_scope)) -> CoverageMatrixOut:
    countries = [
        {"iso2": c.iso2, "name": c.name, "route": c.pooling_route,
         "exchange_control": c.exchange_control}
        for c in scope.session.execute(select(Country).order_by(Country.iso2)).scalars()
    ]
    banks = [
        {"id": b.id, "name": b.name, "tier": b.tier, "panel_status": b.panel_status}
        for b in scope.session.execute(select(Bank).order_by(Bank.id)).scalars()
    ]
    grid: dict[str, dict[str, bool]] = {b["id"]: {} for b in banks}
    for bank_id, iso2, can_serve in scope.session.execute(
        select(
            BankCountryCoverage.bank_id,
            BankCountryCoverage.country_iso2,
            BankCountryCoverage.can_serve,
        )
    ).all():
        grid.setdefault(bank_id, {})[iso2] = bool(can_serve)

    return CoverageMatrixOut(countries=countries, banks=banks, grid=grid)


@router.get("/balances", response_model=list[BalanceOut], summary="Daily snapshot")
def list_balances(
    scope: Scope = Depends(current_scope),
    as_of: str | None = Query(default=None, max_length=10),
    entity: str | None = Query(default=None, max_length=32),
) -> list[BalanceOut]:
    scope.require_amounts()
    if entity:
        scope.require(entity)

    from datetime import date as date_type

    day = date_type.fromisoformat(as_of) if as_of else scope.as_of
    fx = metrics.FxBook(scope.session, day)

    query = (
        select(Balance, Account)
        .join(Account, Account.id == Balance.account_id)
        .where(Balance.as_of == day, Account.entity_id.in_(scope.entity_ids))
        .order_by(Balance.account_id)
    )
    if entity:
        query = query.where(Account.entity_id == entity)

    return [
        BalanceOut(
            account_id=balance.account_id,
            entity_id=account.entity_id,
            as_of=balance.as_of,
            opening=money_native(balance.opening_native, account.currency, fx.rate(account.currency)),
            closing=money_native(balance.closing_native, account.currency, fx.rate(account.currency)),
            value_dated=money_native(
                balance.value_dated_native, account.currency, fx.rate(account.currency)
            ),
            ingested_at=balance.ingested_at,
            feed_status=account.feed_status,
        )
        for balance, account in scope.session.execute(query).all()
    ]


@router.get("/facilities", response_model=list[FacilityOut], summary="Debt and headroom")
def list_facilities(scope: Scope = Depends(current_scope)) -> list[FacilityOut]:
    scope.require_amounts()
    fx = metrics.FxBook(scope.session, scope.as_of)

    rows = scope.session.execute(
        select(Facility, Bank.name)
        .join(Bank, Bank.id == Facility.bank_id)
        .where(Facility.entity_id.in_(scope.entity_ids))
        .order_by(Facility.id)
    ).all()

    return [
        FacilityOut(
            id=facility.id,
            entity_id=facility.entity_id,
            bank_id=facility.bank_id,
            bank_name=bank_name,
            kind=facility.kind,
            committed=money_native(
                facility.committed_native, facility.currency, fx.rate(facility.currency)
            ),
            drawn=money_native(
                facility.drawn_native, facility.currency, fx.rate(facility.currency)
            ),
            headroom=money_native(
                facility.committed_native - facility.drawn_native,
                facility.currency,
                fx.rate(facility.currency),
            ),
            benchmark=facility.benchmark,
            spread_bps=facility.spread_bps,
            all_in_rate=facility.all_in_rate,
            maturity=facility.maturity,
            covenant_note=facility.covenant_note,
        )
        for facility, bank_name in rows
    ]
