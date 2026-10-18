"""Thirteen-week forecast read and submission."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ..models import Entity, Forecast, ForecastLine, Persona
from ..repositories.scope import Scope, current_scope
from ..schemas.treasury import ForecastLineOut, ForecastOut, ForecastSubmission
from ..services import audit as audit_service
from ..services import metrics
from .helpers import money_native
from ..auth import Principal, guard_write

router = APIRouter(tags=["forecasts"])

CATEGORIES = ("receipts", "payroll", "suppliers", "tax", "capex", "debt_service", "other")

OWNER_BY_ENTITY_DEFAULT = "Local Coordinator"


def _accuracy(amount: float, actual: float | None) -> float | None:
    if actual in (None, 0):
        return None
    error = abs(amount - actual) / max(abs(actual), 1.0)
    return max(0.0, 1.0 - error)


def _forecast_out(scope: Scope, forecast: Forecast, currency: str, fx: float) -> ForecastOut:
    lines = list(
        scope.session.execute(
            select(ForecastLine)
            .where(ForecastLine.forecast_id == forecast.id)
            .order_by(ForecastLine.week_offset, ForecastLine.category)
        ).scalars()
    )

    net: dict[int, float] = {}
    scored: list[float] = []
    out_lines: list[ForecastLineOut] = []

    for line in lines:
        net[line.week_offset] = net.get(line.week_offset, 0.0) + line.amount_native
        accuracy = _accuracy(line.amount_native, line.actual_native)
        if accuracy is not None:
            scored.append(accuracy)
        out_lines.append(
            ForecastLineOut(
                week_offset=line.week_offset,
                category=line.category,
                amount=money_native(line.amount_native, currency, fx),
                actual=(
                    money_native(line.actual_native, currency, fx)
                    if line.actual_native is not None
                    else None
                ),
                accuracy=accuracy,
            )
        )

    owner = scope.session.execute(
        select(Persona.holder_name).where(
            Persona.scope_kind == "entity", Persona.scope_ref == forecast.entity_id
        )
    ).scalar_one_or_none()

    return ForecastOut(
        id=forecast.id,
        entity_id=forecast.entity_id,
        cycle_year=forecast.cycle_year,
        cycle_week=forecast.cycle_week,
        horizon_weeks=forecast.horizon_weeks,
        status=forecast.status,
        submitted_at=forecast.submitted_at,
        submitted_by=forecast.submitted_by,
        reviewed_by=forecast.reviewed_by,
        lines=out_lines,
        net_by_week=[
            money_native(net.get(week, 0.0), currency, fx)
            for week in range(forecast.horizon_weeks)
        ],
        accuracy=(sum(scored) / len(scored)) if scored else None,
        owner=owner or OWNER_BY_ENTITY_DEFAULT,
    )


@router.get(
    "/forecasts/{entity_id}",
    response_model=list[ForecastOut],
    summary="13-week forecast with actuals",
)
def get_forecasts(entity_id: str, scope: Scope = Depends(current_scope)) -> list[ForecastOut]:
    scope.require_amounts()
    scope.require(entity_id)

    entity = scope.session.get(Entity, entity_id)
    fx = metrics.FxBook(scope.session, scope.as_of)

    return [
        _forecast_out(scope, forecast, entity.functional_ccy, fx.rate(entity.functional_ccy))
        for forecast in scope.session.execute(
            select(Forecast)
            .where(Forecast.entity_id == entity_id)
            .order_by(Forecast.cycle_year.desc(), Forecast.cycle_week.desc())
        ).scalars()
    ]


@router.post(
    "/forecasts/{entity_id}",
    response_model=ForecastOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a cycle. A local coordinator may submit for their own entity only",
)
def submit_forecast(
    entity_id: str, submission: ForecastSubmission, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),
) -> ForecastOut:
    scope.require(entity_id)

    # LR10 at the boundary: an entity-scoped persona may only ever write to its
    # own entity, and that is checked here rather than trusted from the client.
    if scope.persona.scope_kind == "entity" and scope.persona.scope_ref != entity_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://gcpl.local/problems/out-of-scope",
                "title": "This entity is outside your scope.",
                "status": 403,
                "detail": (
                    f"{scope.persona.display_name} submits for "
                    f"{scope.persona.scope_ref} only."
                ),
                "instance": f"/forecasts/{entity_id}",
            },
        )
    if scope.persona.scope_kind not in {"entity", "region", "group"}:
        scope.require_persona_in({"P5"}, "submit a forecast cycle")

    entity = scope.session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="No such entity.")

    forecast_id = (
        f"FC-{entity_id}-{submission.cycle_year}W{submission.cycle_week:02d}"
    )
    existing = scope.session.get(Forecast, forecast_id)
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if existing is None:
        existing = Forecast(
            id=forecast_id,
            entity_id=entity_id,
            cycle_week=submission.cycle_week,
            cycle_year=submission.cycle_year,
            horizon_weeks=13,
        )
        scope.session.add(existing)
        scope.session.flush()
    else:
        scope.session.query(ForecastLine).filter(
            ForecastLine.forecast_id == forecast_id
        ).delete()

    existing.submitted_at = stamp
    existing.submitted_by = scope.persona.id
    existing.status = "submitted"

    for raw in submission.lines:
        week = int(raw.get("week_offset", 0))
        category = str(raw.get("category", "other"))
        if category not in CATEGORIES or not 0 <= week < 13:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "type": "https://gcpl.local/problems/invalid-forecast-line",
                    "title": "Invalid forecast line.",
                    "status": 422,
                    "detail": (
                        f"week_offset must be 0 to 12 and category one of "
                        f"{', '.join(CATEGORIES)}. Received week {week}, "
                        f"category '{category}'."
                    ),
                    "instance": f"/forecasts/{entity_id}",
                },
            )
        scope.session.add(
            ForecastLine(
                forecast_id=forecast_id,
                week_offset=week,
                category=category,
                amount_native=float(raw.get("amount_native", 0.0)),
                actual_native=None,
            )
        )

    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="FORECAST_SUBMITTED",
        obj_kind="forecast",
        obj_id=forecast_id,
        detail=(
            f"{len(submission.lines)} lines submitted for "
            f"{submission.cycle_year} week {submission.cycle_week}."
        ),
        justification=submission.justification,
    )
    scope.session.commit()

    fx = metrics.FxBook(scope.session, scope.as_of)
    return _forecast_out(
        scope, existing, entity.functional_ccy, fx.rate(entity.functional_ccy)
    )
