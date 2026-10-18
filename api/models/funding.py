"""Debt facilities and the deposit rates they are compared against."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Facility(Base):
    __tablename__ = "facility"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    bank_id: Mapped[str] = mapped_column(ForeignKey("bank.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    committed_native: Mapped[float] = mapped_column(Float, nullable=False)
    drawn_native: Mapped[float] = mapped_column(Float, nullable=False)
    benchmark: Mapped[str] = mapped_column(String, nullable=False)
    spread_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    all_in_rate: Mapped[float] = mapped_column(Float, nullable=False)
    maturity: Mapped[date] = mapped_column(Date, nullable=False)
    covenant_note: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('rcf','term','overdraft','trade','commercial_paper')",
            name="ck_facility_kind",
        ),
    )


class DepositRate(Base):
    __tablename__ = "deposit_rate"

    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), primary_key=True)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
