"""Counterparty limits and market exposures."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CounterpartyLimit(Base):
    __tablename__ = "counterparty_limit"

    bank_id: Mapped[str] = mapped_column(ForeignKey("bank.id"), primary_key=True)
    limit_kind: Mapped[str] = mapped_column(String, primary_key=True)
    limit_usd: Mapped[float] = mapped_column(Float, nullable=False)
    utilised_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        CheckConstraint(
            "limit_kind IN ('cash','facility','derivative')", name="ck_limit_kind"
        ),
    )


class Exposure(Base):
    __tablename__ = "exposure"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    currency_pair: Mapped[str | None] = mapped_column(String)
    notional_usd: Mapped[float] = mapped_column(Float, nullable=False)
    hedged_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('fx_transaction','fx_translation','interest_rate','commodity')",
            name="ck_exposure_kind",
        ),
    )
