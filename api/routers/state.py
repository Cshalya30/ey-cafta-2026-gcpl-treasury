"""Bootstrap, personas, routes, KPIs and the programme."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from ..models import Currency, Entity, Gate, Region, Wave
from ..repositories.scope import Scope, current_scope
from ..schemas.common import Coverage, CitationOut, PersonaOut, RouteOut
from ..schemas.treasury import (
    GateOut,
    GroupSummary,
    KpiOut,
    ProgrammeOut,
    RegionOut,
    StateOut,
    WaveOut,
)
from ..services import metrics, routing
from .helpers import money_from_usd

router = APIRouter(tags=["state"])

WATERMARK = (
    "SYNTHETIC DATA // DEMO TENANT FOR EY CAFTA 2026 // DO NOT RELY FOR LIVE TRANSFERS"
)


def _summary(scope: Scope) -> GroupSummary:
    raw = metrics.group_summary(scope.session, set(scope.entity_ids), scope.as_of)
    return GroupSummary(
        as_of=raw["as_of"],
        entity_count=raw["entity_count"],
        total_cash=money_from_usd(raw["total_cash_usd"]),
        available_local=money_from_usd(raw["available_local_usd"]),
        restricted=money_from_usd(raw["restricted_usd"]),
        operating_buffer=money_from_usd(raw["operating_buffer_usd"]),
        deployable_surplus=money_from_usd(raw["deployable_surplus_usd"]),
        drawn=money_from_usd(raw["drawn_usd"]),
        committed=money_from_usd(raw["committed_usd"]),
        coverage=Coverage(**raw["coverage"]),
    )


@router.get("/state", response_model=StateOut, summary="Bootstrap the shell")
def get_state(scope: Scope = Depends(current_scope)) -> StateOut:
    counts = dict(
        scope.session.execute(
            select(Entity.region_id, func.count())
            .where(Entity.id.in_(scope.entity_ids))
            .group_by(Entity.region_id)
        ).all()
    )
    regions = [
        RegionOut(
            id=r.id,
            name=r.name,
            hub_city=r.hub_city,
            hub_lead=r.hub_lead,
            coverage_hours=r.coverage_hours,
            utc_offset=r.utc_offset,
            mandate=r.mandate,
            entity_count=int(counts.get(r.id, 0)),
        )
        for r in scope.session.execute(select(Region).order_by(Region.id)).scalars()
    ]

    return StateOut(
        as_of=scope.as_of.isoformat(),
        persona=PersonaOut.model_validate(scope.persona),
        scope_entity_ids=sorted(scope.entity_ids),
        regions=regions,
        summary=_summary(scope) if scope.sees_amounts else None,
        currencies=[
            c for c in scope.session.execute(select(Currency.code).order_by(Currency.code)).scalars()
        ],
        usd_to_inr=round(metrics.FxBook(scope.session, scope.as_of).usd_per_unit_inverse("INR"), 6),
        watermark=WATERMARK,
        feature_flags={
            "pooling_workbench": True,
            "workflow_studio": True,
            "chain_verification": True,
            "payment_initiation": False,
        },
    )


@router.get("/personas", response_model=list[PersonaOut], summary="All ten personas")
def list_personas(scope: Scope = Depends(current_scope)) -> list[PersonaOut]:
    from ..models import Persona

    return [
        PersonaOut.model_validate(p)
        for p in scope.session.execute(select(Persona).order_by(Persona.id)).scalars()
    ]


@router.get("/routes", response_model=list[RouteOut], summary="The four routing models")
def list_routes(scope: Scope = Depends(current_scope)) -> list[RouteOut]:
    return [
        RouteOut(
            code=route.code,
            name=route.name,
            scope=route.scope,
            mechanism=route.mechanism,
            binding_constraint=route.binding_constraint,
            permits_movement=route.permits_movement,
            citations=[CitationOut(**c.__dict__) for c in route.citations],
        )
        for route in routing.ROUTES.values()
    ]


@router.get("/routes/notional-pooling", summary="The precise notional-pooling statement")
def notional_pooling(scope: Scope = Depends(current_scope)) -> dict:
    """The statement the UI must render, with its three blocking citations.

    Never "RBI prohibits notional pooling"; that is unsupportable.
    """
    return {
        "statement": routing.NOTIONAL_POOLING_STATEMENT,
        "citations": [c.__dict__ for c in routing.NOTIONAL_POOLING_CITATIONS],
        "gift_city_caveat": routing.GIFT_CITY_CAVEAT,
        "safe_harbour_note": routing.RULE_10TD_NOTE,
    }


@router.get("/kpis", response_model=list[KpiOut], summary="The nine KPIs, all computed")
def list_kpis(scope: Scope = Depends(current_scope)) -> list[KpiOut]:
    scope.require_amounts()
    return [
        KpiOut(
            code=k.code,
            label=k.label,
            value=k.value,
            target=k.target,
            unit=k.unit,
            as_of=k.as_of,
            source=k.source,
            stale_count=k.stale_count,
            direction=k.direction,
            on_target=k.on_target,
        )
        for k in metrics.kpis(scope.session, scope.as_of)
    ]


@router.get("/waves", response_model=ProgrammeOut, summary="Programme waves and gates")
def list_waves(scope: Scope = Depends(current_scope)) -> ProgrammeOut:
    waves = [
        WaveOut.model_validate(w)
        for w in scope.session.execute(select(Wave).order_by(Wave.start_month, Wave.id)).scalars()
    ]
    gates = [
        GateOut.model_validate(g)
        for g in scope.session.execute(select(Gate).order_by(Gate.month)).scalars()
    ]
    return ProgrammeOut(
        waves=waves,
        gates=gates,
        horizon_months=max((w.end_month for w in waves), default=18),
    )
