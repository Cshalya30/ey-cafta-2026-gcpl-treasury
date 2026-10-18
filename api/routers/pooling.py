"""Pools, the Cash Leak, and the proposal lifecycle with its SoD gates."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from ..models import Account, Entity, Pool, PoolMember, Proposal, ProposalCheck
from ..repositories.scope import Scope, current_scope
from ..schemas.common import CitationOut, Coverage, RouteOut
from ..schemas.treasury import (
    CashLeakOut,
    CheckOut,
    Decision,
    Economics,
    EvaluateRequest,
    EvaluateResponse,
    LeakExclusionOut,
    LeakPairOut,
    PoolMemberOut,
    PoolOut,
    ProposalCreate,
    ProposalOut,
)
from ..services import audit as audit_service
from ..services import metrics, pooling, routing, sod
from .helpers import money_from_usd, money_native
from ..auth import Principal, guard_write

router = APIRouter(tags=["pooling"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _route_out(code: str) -> RouteOut:
    route = routing.ROUTES[code]
    return RouteOut(
        code=route.code,
        name=route.name,
        scope=route.scope,
        mechanism=route.mechanism,
        binding_constraint=route.binding_constraint,
        permits_movement=route.permits_movement,
        citations=[CitationOut(**c.__dict__) for c in route.citations],
    )


# ───────────────────────── pools ─────────────────────────


@router.get("/pools", response_model=list[PoolOut], summary="Pool designs and status")
def list_pools(scope: Scope = Depends(current_scope)) -> list[PoolOut]:
    fx = metrics.FxBook(scope.session, scope.as_of)
    currencies = dict(scope.session.execute(select(Entity.id, Entity.functional_ccy)).all())

    members: dict[str, list[PoolMemberOut]] = {}
    for row in scope.session.execute(
        select(PoolMember).order_by(PoolMember.pool_id, PoolMember.account_id)
    ).scalars():
        if row.entity_id not in scope.entity_ids:
            continue
        ccy = currencies.get(row.entity_id, "USD")
        members.setdefault(row.pool_id, []).append(
            PoolMemberOut(
                entity_id=row.entity_id,
                account_id=row.account_id,
                sweep_target=money_native(row.sweep_target_native, ccy, fx.rate(ccy)),
            )
        )

    return [
        PoolOut(
            id=pool.id,
            name=pool.name,
            kind=pool.kind,
            header_entity_id=pool.header_entity_id,
            header_bank_id=pool.header_bank_id,
            currency=pool.currency,
            route=pool.route,
            route_detail=_route_out(pool.route),
            legal_cleared_by=pool.legal_cleared_by,
            tax_cleared_by=pool.tax_cleared_by,
            status=pool.status,
            members=members.get(pool.id, []),
        )
        for pool in scope.session.execute(select(Pool).order_by(Pool.id)).scalars()
    ]


# ───────────────────────── the Cash Leak ─────────────────────────


@router.get("/cash-leak", response_model=CashLeakOut, summary="The headline number")
def cash_leak(scope: Scope = Depends(current_scope)) -> CashLeakOut:
    """Every figure here is computed. Change a deposit rate and reload: it moves."""
    scope.require_amounts()
    raw = metrics.cash_leak(scope.session, scope.as_of)
    financials = metrics.entity_financials(scope.session, scope.as_of)

    pairs = [
        LeakPairOut(
            surplus_entity=p.surplus_entity,
            surplus_deployable=money_native(
                p.surplus_deployable_native,
                p.surplus_currency,
                p.surplus_deployable_usd / p.surplus_deployable_native
                if p.surplus_deployable_native
                else 1.0,
            ),
            deposit_rate=p.deposit_rate,
            borrowing_entity=p.borrowing_entity,
            drawn=money_native(
                p.drawn_native,
                p.borrowing_currency,
                p.drawn_usd / p.drawn_native if p.drawn_native else 1.0,
            ),
            all_in_rate=p.all_in_rate,
            benchmark=p.benchmark,
            route=p.route,
            overlap_usd=p.overlap_usd,
            spread=p.spread,
            annualised_leak_usd=p.annualised_leak_usd,
            detail=p.detail,
            blocked_by=p.blocked_by,
        )
        for p in raw["pairs"]
        if p.surplus_entity in scope.entity_ids and p.borrowing_entity in scope.entity_ids
    ]

    accounts = sum(f.account_count for k, f in financials.items() if k in scope.entity_ids)
    current = sum(f.live_accounts for k, f in financials.items() if k in scope.entity_ids)

    return CashLeakOut(
        as_of=raw["as_of"],
        total_annualised_usd=round(sum(p.annualised_leak_usd for p in pairs), 2),
        method=raw["method"],
        pairs=pairs,
        excluded=[
            LeakExclusionOut(entity=e.entity, reason=e.reason, trapped_usd=e.trapped_usd)
            for e in raw["excluded"]
            if e.entity in scope.entity_ids
        ],
        coverage=Coverage(
            accounts_total=accounts,
            accounts_current=current,
            pct=(current / accounts) if accounts else 0.0,
            statement=f"{current} of {accounts} accounts current",
        ),
    )


# ───────────────────────── proposals ─────────────────────────


def _economics(
    scope: Scope, source_id: str, target_id: str, amount_usd: float, tenor_days: int,
    interest_rate: float, rating_band: str,
) -> Economics:
    """Recomputed from the caller's parameters on every call. Never stored."""
    financials = metrics.entity_financials(scope.session, scope.as_of)
    source = financials[source_id]
    target = financials[target_id]
    fx = metrics.FxBook(scope.session, scope.as_of)

    harbour = routing.safe_harbour_floor(
        source.currency, rating_band, amount_usd, fx.usd_per_unit_inverse("INR")
    )
    all_in = target.all_in_rate or 0.0
    spread = all_in - source.deposit_rate
    annual = amount_usd * spread
    period = annual * (tenor_days / 365.0)

    return Economics(
        source_deposit_rate=source.deposit_rate,
        target_all_in_rate=all_in,
        spread=round(spread, 6),
        annual_saving_usd=round(annual, 2),
        period_saving_usd=round(period, 2),
        safe_harbour_floor=harbour.floor,
        safe_harbour_basis=harbour.basis,
        safe_harbour_citation=harbour.citation,
        workings=(
            f"{amount_usd:,.0f} USD x ({all_in:.4f} target all-in - "
            f"{source.deposit_rate:.4f} source deposit) = {annual:,.0f} USD per year; "
            f"over {tenor_days} days that is {period:,.0f} USD. Proposed rate "
            f"{interest_rate:.4f} against a safe-harbour floor of {harbour.floor:.4f}."
        ),
    )


@router.post(
    "/proposals/evaluate",
    response_model=EvaluateResponse,
    summary="Dry-run the nine checks without creating anything",
)
def evaluate(request: EvaluateRequest, scope: Scope = Depends(current_scope)) -> EvaluateResponse:
    """Powers the Workbench sliders. Creates nothing and writes no audit event."""
    scope.require_amounts()
    scope.require(request.source_entity_id)
    scope.require(request.target_entity_id)

    draft = pooling.ProposalDraft(
        kind=request.kind,
        source_entity_id=request.source_entity_id,
        target_entity_id=request.target_entity_id,
        amount_usd=request.amount_usd,
        tenor_days=request.tenor_days,
        interest_rate=request.interest_rate,
        rating_band=request.rating_band,
    )
    results = pooling.evaluate(scope.session, draft, scope.persona, scope.as_of)

    return EvaluateResponse(
        as_of=scope.as_of.isoformat(),
        checks=[CheckOut(**r.__dict__) for r in results],
        verdict=pooling.verdict(results),
        blocking_count=sum(1 for r in results if r.result == "ERR"),
        warning_count=sum(1 for r in results if r.result == "WARN"),
        economics=_economics(
            scope,
            request.source_entity_id,
            request.target_entity_id,
            request.amount_usd,
            request.tenor_days,
            request.interest_rate,
            request.rating_band,
        ),
    )


def _proposal_out(scope: Scope, proposal: Proposal) -> ProposalOut:
    checks = [
        CheckOut(check_no=c.check_no, code=c.code, result=c.result, detail=c.detail)
        for c in scope.session.execute(
            select(ProposalCheck)
            .where(ProposalCheck.proposal_id == proposal.id)
            .order_by(ProposalCheck.check_no)
        ).scalars()
    ]
    return ProposalOut(
        id=proposal.id,
        kind=proposal.kind,
        source_entity_id=proposal.source_entity_id,
        target_entity_id=proposal.target_entity_id,
        amount=money_from_usd(proposal.amount_usd),
        tenor_days=proposal.tenor_days,
        route=proposal.route,
        interest_rate=proposal.interest_rate,
        rate_basis=proposal.rate_basis,
        created_by=proposal.created_by,
        created_at=proposal.created_at,
        approved_by=proposal.approved_by,
        approved_at=proposal.approved_at,
        settled_by=proposal.settled_by,
        settled_at=proposal.settled_at,
        status=proposal.status,
        checks=checks,
        blocking_count=sum(1 for c in checks if c.result == "ERR"),
        warning_count=sum(1 for c in checks if c.result == "WARN"),
    )


@router.get("/proposals", response_model=list[ProposalOut], summary="Proposal blotter")
def list_proposals(
    scope: Scope = Depends(current_scope),
    proposal_status: str | None = Query(default=None, alias="status", max_length=24),
) -> list[ProposalOut]:
    scope.require_amounts()
    query = (
        select(Proposal)
        .where(
            Proposal.source_entity_id.in_(scope.entity_ids),
            Proposal.target_entity_id.in_(scope.entity_ids),
        )
        .order_by(Proposal.created_at.desc(), Proposal.id.desc())
    )
    if proposal_status:
        query = query.where(Proposal.status == proposal_status)
    return [_proposal_out(scope, p) for p in scope.session.execute(query).scalars()]


@router.get("/proposals/{proposal_id}", response_model=ProposalOut, summary="One proposal")
def get_proposal(proposal_id: str, scope: Scope = Depends(current_scope)) -> ProposalOut:
    scope.require_amounts()
    proposal = scope.session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal.")
    scope.require(proposal.source_entity_id)
    return _proposal_out(scope, proposal)


@router.post(
    "/proposals",
    response_model=ProposalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a proposal and run all nine checks synchronously",
)
def create_proposal(
    request: ProposalCreate, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),
) -> ProposalOut:
    scope.require_capability("initiate")
    scope.require(request.source_entity_id)
    scope.require(request.target_entity_id)

    draft = pooling.ProposalDraft(
        kind=request.kind,
        source_entity_id=request.source_entity_id,
        target_entity_id=request.target_entity_id,
        amount_usd=request.amount_usd,
        tenor_days=request.tenor_days,
        interest_rate=request.interest_rate,
        rate_basis=request.rate_basis,
        rating_band=request.rating_band,
    )
    results = pooling.evaluate(scope.session, draft, scope.persona, scope.as_of)
    verdict = pooling.verdict(results)

    if verdict == "checks_failed":
        blocking = [r for r in results if r.result == "ERR"]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "https://gcpl.local/problems/checks-failed",
                "title": "This proposal fails one or more blocking checks.",
                "status": 422,
                "detail": " ".join(f"[{r.code}] {r.detail}" for r in blocking),
                "instance": "/proposals",
            },
        )

    serial = scope.session.execute(select(func.count()).select_from(Proposal)).scalar_one()
    proposal_id = f"PRP-{serial + 1:04d}"
    stamp = _now()
    source_country = scope.session.get(Entity, request.source_entity_id).country_iso2
    target_country = scope.session.get(Entity, request.target_entity_id).country_iso2

    proposal = Proposal(
        id=proposal_id,
        kind=request.kind,
        source_entity_id=request.source_entity_id,
        target_entity_id=request.target_entity_id,
        amount_usd=request.amount_usd,
        tenor_days=request.tenor_days,
        route=metrics.pair_route(source_country, target_country),
        interest_rate=request.interest_rate,
        rate_basis=request.rate_basis,
        created_by=scope.persona.id,
        created_at=stamp,
        status=verdict,
    )
    scope.session.add(proposal)
    scope.session.flush()

    for result in results:
        scope.session.add(
            ProposalCheck(
                proposal_id=proposal_id,
                check_no=result.check_no,
                code=result.code,
                result=result.result,
                detail=result.detail,
                evaluated_at=stamp,
            )
        )

    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="PROPOSAL_CREATED",
        obj_kind="proposal",
        obj_id=proposal_id,
        detail=(
            f"{request.kind} of {request.amount_usd:,.0f} USD from "
            f"{request.source_entity_id} to {request.target_entity_id} at "
            f"{request.interest_rate:.2%} for {request.tenor_days} days."
        ),
        justification=request.justification,
    )
    scope.session.commit()
    return _proposal_out(scope, scope.session.get(Proposal, proposal_id))


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ProposalOut,
    summary="Approve. Rejected if the approver is the creator (LR1)",
)
def approve_proposal(
    proposal_id: str, decision: Decision, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),
) -> ProposalOut:
    scope.require_capability("approve")
    proposal = scope.session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal.")
    scope.require(proposal.source_entity_id)

    if proposal.status != "pending_auth":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://gcpl.local/problems/wrong-state",
                "title": "This proposal is not awaiting authorisation.",
                "status": 409,
                "detail": f"Proposal {proposal_id} is {proposal.status}.",
                "instance": f"/proposals/{proposal_id}/approve",
            },
        )

    # LR1, evaluated by the real linter against the proposed end state.
    proposal.approved_by = scope.persona.id
    violations = sod.lint_proposal(scope.session, proposal, scope.persona)
    blocking = [v for v in violations if v.blocking]
    if blocking:
        proposal.approved_by = None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://gcpl.local/problems/sod-violation",
                "title": "Segregation of duties blocks this approval.",
                "status": 403,
                "detail": " ".join(f"[{v.rule_id}] {v.detail}" for v in blocking),
                "instance": f"/proposals/{proposal_id}/approve",
            },
        )

    proposal.approved_at = _now()
    proposal.status = "authorised"
    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="PROPOSAL_APPROVED",
        obj_kind="proposal",
        obj_id=proposal_id,
        detail=f"Approved by {scope.persona.id}, creator was {proposal.created_by}.",
        justification=decision.justification,
    )
    scope.session.commit()
    return _proposal_out(scope, proposal)


@router.post(
    "/proposals/{proposal_id}/settle",
    response_model=ProposalOut,
    summary="Settle. Rejected if the settler created or approved it (LR4)",
)
def settle_proposal(
    proposal_id: str, decision: Decision, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),
) -> ProposalOut:
    scope.require_capability("settle")
    proposal = scope.session.get(Proposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="No such proposal.")
    scope.require(proposal.source_entity_id)

    if proposal.status != "authorised":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://gcpl.local/problems/wrong-state",
                "title": "Only an authorised proposal can be settled.",
                "status": 409,
                "detail": f"Proposal {proposal_id} is {proposal.status}.",
                "instance": f"/proposals/{proposal_id}/settle",
            },
        )

    proposal.settled_by = scope.persona.id
    violations = sod.lint_proposal(scope.session, proposal, scope.persona)
    blocking = [v for v in violations if v.blocking]
    if blocking:
        proposal.settled_by = None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://gcpl.local/problems/sod-violation",
                "title": "Segregation of duties blocks this settlement.",
                "status": 403,
                "detail": " ".join(f"[{v.rule_id}] {v.detail}" for v in blocking),
                "instance": f"/proposals/{proposal_id}/settle",
            },
        )

    proposal.settled_at = _now()
    proposal.status = "settled"
    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="PROPOSAL_SETTLED",
        obj_kind="proposal",
        obj_id=proposal_id,
        detail=(
            f"Settled by {scope.persona.id}, independent of creator "
            f"{proposal.created_by} and approver {proposal.approved_by}."
        ),
        justification=decision.justification,
    )
    scope.session.commit()
    return _proposal_out(scope, proposal)
