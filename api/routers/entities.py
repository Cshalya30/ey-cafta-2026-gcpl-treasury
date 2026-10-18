"""Entity list, Entity 360, the group view, onboarding and exposures."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..models import Entity, Exposure, OnboardingItem
from ..repositories.scope import Scope, current_scope
from ..schemas.treasury import EntityOut, ExposureOut, GroupViewOut, OnboardingItemOut
from ..services import metrics
from .helpers import country_names, entity_payload

router = APIRouter(tags=["entities"])


def _entities_in_scope(
    scope: Scope,
    region: str | None = None,
    pool_status: str | None = None,
    onboard_status: str | None = None,
) -> list[EntityOut]:
    financials = metrics.entity_financials(scope.session, scope.as_of)
    names = country_names(scope.session)

    query = select(Entity).where(Entity.id.in_(scope.entity_ids)).order_by(Entity.id)
    if region:
        query = query.where(Entity.region_id == region)
    if pool_status:
        query = query.where(Entity.pool_status == pool_status)
    if onboard_status:
        query = query.where(Entity.onboard_status == onboard_status)

    return [
        entity_payload(entity, financials[entity.id], names.get(entity.country_iso2, ""))
        for entity in scope.session.execute(query).scalars()
    ]


@router.get("/entities", response_model=list[EntityOut], summary="Entities in scope")
def list_entities(
    scope: Scope = Depends(current_scope),
    region: str | None = Query(default=None, max_length=16),
    pool_status: str | None = Query(default=None, max_length=16),
    onboard_status: str | None = Query(default=None, max_length=24),
) -> list[EntityOut]:
    scope.require_amounts()
    return _entities_in_scope(scope, region, pool_status, onboard_status)


@router.get("/entities/{entity_id}", response_model=EntityOut, summary="Entity 360")
def get_entity(entity_id: str, scope: Scope = Depends(current_scope)) -> EntityOut:
    scope.require_amounts()
    scope.require(entity_id)
    entity = scope.session.get(Entity, entity_id)
    financials = metrics.entity_financials(scope.session, scope.as_of)
    names = country_names(scope.session)
    return entity_payload(entity, financials[entity_id], names.get(entity.country_iso2, ""))


@router.get(
    "/entities/{entity_id}/group-view",
    response_model=GroupViewOut,
    summary="Exactly what the group sees about this entity",
)
def get_group_view(entity_id: str, scope: Scope = Depends(current_scope)) -> GroupViewOut:
    """Produced by the same function that serves the CFO, never a restatement."""
    scope.require_amounts()
    scope.require(entity_id)
    entity = scope.session.get(Entity, entity_id)
    financials = metrics.entity_financials(scope.session, scope.as_of)
    names = country_names(scope.session)
    return GroupViewOut(
        entity=entity_payload(entity, financials[entity_id], names.get(entity.country_iso2, ""))
    )


@router.get(
    "/entities/{entity_id}/onboarding",
    response_model=list[OnboardingItemOut],
    summary="The seven-item Day-1 kit",
)
def get_onboarding(
    entity_id: str, scope: Scope = Depends(current_scope)
) -> list[OnboardingItemOut]:
    scope.require(entity_id)
    return [
        OnboardingItemOut.model_validate(item)
        for item in scope.session.execute(
            select(OnboardingItem)
            .where(OnboardingItem.entity_id == entity_id)
            .order_by(OnboardingItem.item_no)
        ).scalars()
    ]


@router.get(
    "/exposures", response_model=list[ExposureOut], summary="FX and rate exposures in scope"
)
def list_exposures(
    scope: Scope = Depends(current_scope),
    entity: str | None = Query(default=None, max_length=32),
) -> list[ExposureOut]:
    scope.require_amounts()
    if entity:
        scope.require(entity)

    query = (
        select(Exposure)
        .where(Exposure.entity_id.in_(scope.entity_ids), Exposure.as_of == scope.as_of)
        .order_by(Exposure.id)
    )
    if entity:
        query = query.where(Exposure.entity_id == entity)

    out: list[ExposureOut] = []
    for row in scope.session.execute(query).scalars():
        unhedged = row.notional_usd - row.hedged_usd
        out.append(
            ExposureOut(
                id=row.id,
                entity_id=row.entity_id,
                kind=row.kind,
                currency_pair=row.currency_pair,
                notional_usd=round(row.notional_usd, 2),
                hedged_usd=round(row.hedged_usd, 2),
                unhedged_usd=round(unhedged, 2),
                hedge_ratio=(row.hedged_usd / row.notional_usd) if row.notional_usd else 0.0,
                as_of=row.as_of,
            )
        )
    return out
