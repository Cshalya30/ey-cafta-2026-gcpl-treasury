"""Reference data: currencies, FX, countries, regions."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Currency(Base):
    __tablename__ = "currency"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    minor_units: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    symbol: Mapped[str] = mapped_column(String, nullable=False)


class FxRate(Base):
    __tablename__ = "fx_rate"

    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    base: Mapped[str] = mapped_column(ForeignKey("currency.code"), primary_key=True)
    quote: Mapped[str] = mapped_column(ForeignKey("currency.code"), primary_key=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)


class Region(Base):
    __tablename__ = "region"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hub_city: Mapped[str] = mapped_column(String, nullable=False)
    hub_lead: Mapped[str] = mapped_column(String, nullable=False)
    coverage_hours: Mapped[str] = mapped_column(String, nullable=False)
    utc_offset: Mapped[float] = mapped_column(Float, nullable=False)
    mandate: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("mandate IN ('delegated','reserved')", name="ck_region_mandate"),
    )


class Country(Base):
    __tablename__ = "country"

    iso2: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    region_id: Mapped[str] = mapped_column(ForeignKey("region.id"), nullable=False)
    exchange_control: Mapped[str] = mapped_column(String, nullable=False)
    pooling_route: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        CheckConstraint(
            "exchange_control IN ('none','monitored','restricted')",
            name="ck_country_exchange_control",
        ),
        CheckConstraint("pooling_route IN ('A','B','C','D')", name="ck_country_route"),
    )
