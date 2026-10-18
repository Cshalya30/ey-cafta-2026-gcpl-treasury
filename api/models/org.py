"""Legal-entity structure."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Entity(Base):
    __tablename__ = "entity"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, nullable=False)
    country_iso2: Mapped[str] = mapped_column(ForeignKey("country.iso2"), nullable=False)
    region_id: Mapped[str] = mapped_column(ForeignKey("region.id"), nullable=False)
    functional_ccy: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    erp_system: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("entity.id"))
    ownership_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    is_hq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acquired_on: Mapped[date | None] = mapped_column(Date)
    onboard_status: Mapped[str] = mapped_column(String, nullable=False, default="live")
    pool_status: Mapped[str] = mapped_column(String, nullable=False)
    loc1_certified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operating_buffer_native: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        CheckConstraint(
            "onboard_status IN ('live','onboarding','reporting_only','not_onboarded')",
            name="ck_entity_onboard_status",
        ),
        CheckConstraint(
            "pool_status IN ('eligible','restricted','review','not_assessed')",
            name="ck_entity_pool_status",
        ),
    )
