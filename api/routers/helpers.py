"""Shared conversions between the engines and the wire format."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Country, Entity
from ..schemas.common import Money
from ..schemas.treasury import EntityDecomposition, EntityOut
from ..services.metrics import EntityFinancials


def money_from_usd(usd: float) -> Money:
    """A figure already expressed in USD. Native and USD are the same number."""
    return Money(native=round(usd, 2), currency="USD", usd=round(usd, 2))


def money_native(native: float, currency: str, fx_to_usd: float) -> Money:
    return Money(
        native=round(native, 2), currency=currency, usd=round(native * fx_to_usd, 2)
    )


def country_names(session: Session) -> dict[str, str]:
    return dict(session.execute(select(Country.iso2, Country.name)).all())


def entity_payload(
    entity: Entity, fin: EntityFinancials, country_name: str
) -> EntityOut:
    """The single entity payload. The CFO view and the local group-view share it.

    There is deliberately one function: PRD 8.9 requires the local "what the
    group sees about me" tab to be byte-identical to what the CFO receives, and
    the only reliable way to guarantee that is to have one producer.
    """
    ccy, fx = fin.currency, fin.fx_to_usd
    return EntityOut(
        id=entity.id,
        legal_name=entity.legal_name,
        short_name=entity.short_name,
        country_iso2=entity.country_iso2,
        country_name=country_name,
        region_id=entity.region_id,
        functional_ccy=ccy,
        erp_system=entity.erp_system,
        parent_id=entity.parent_id,
        ownership_pct=entity.ownership_pct,
        is_hq=bool(entity.is_hq),
        acquired_on=entity.acquired_on,
        onboard_status=entity.onboard_status,
        pool_status=entity.pool_status,
        route=fin.route,
        decomposition=EntityDecomposition(
            total_cash=money_native(fin.total_cash_native, ccy, fx),
            restricted=money_native(fin.restricted_native, ccy, fx),
            available_local=money_native(fin.available_local_native, ccy, fx),
            operating_buffer=money_native(fin.operating_buffer_native, ccy, fx),
            deployable_surplus=money_native(fin.deployable_surplus_native, ccy, fx),
        ),
        drawn=money_native(fin.drawn_native, ccy, fx),
        committed=money_native(fin.committed_native, ccy, fx),
        headroom=money_native(fin.committed_native - fin.drawn_native, ccy, fx),
        deposit_rate=fin.deposit_rate,
        all_in_rate=fin.all_in_rate,
        account_count=fin.account_count,
        live_accounts=fin.live_accounts,
        stale_accounts=fin.stale_accounts,
        offline_accounts=fin.offline_accounts,
        coverage_pct=fin.coverage_pct,
    )
