"""Thirteen-week rolling forecast and its actuals."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Forecast(Base):
    __tablename__ = "forecast"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    cycle_week: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=13)
    submitted_at: Mapped[str | None] = mapped_column(String)
    submitted_by: Mapped[str | None] = mapped_column(String)
    reviewed_by: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','challenged','approved')",
            name="ck_forecast_status",
        ),
        UniqueConstraint("entity_id", "cycle_year", "cycle_week", name="uq_forecast_cycle"),
    )


class ForecastLine(Base):
    __tablename__ = "forecast_line"

    forecast_id: Mapped[str] = mapped_column(ForeignKey("forecast.id"), primary_key=True)
    week_offset: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    amount_native: Mapped[float] = mapped_column(Float, nullable=False)
    actual_native: Mapped[float | None] = mapped_column(Float)
