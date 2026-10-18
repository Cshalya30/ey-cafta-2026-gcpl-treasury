"""Transformation programme: waves, gates, the Day-1 kit and KPI snapshots."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Wave(Base):
    __tablename__ = "wave"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)
    end_month: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)


class Gate(Base):
    __tablename__ = "gate"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    criterion: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    __table_args__ = (
        CheckConstraint("status IN ('pending','passed','failed')", name="ck_gate_status"),
    )


class OnboardingItem(Base):
    __tablename__ = "onboarding_item"

    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), primary_key=True)
    item_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    item: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    due_day: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_progress','done','blocked')",
            name="ck_onboarding_item_status",
        ),
    )


class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshot"

    kpi_code: Mapped[str] = mapped_column(String, primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    target: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("unit IN ('pct','usd','count','days')", name="ck_kpi_unit"),
    )
