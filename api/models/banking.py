"""Banks, account estate and daily balances."""

from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Bank(Base):
    __tablename__ = "bank"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    swift_bic: Mapped[str | None] = mapped_column(String)
    connectivity: Mapped[str] = mapped_column(String, nullable=False)
    panel_status: Mapped[str] = mapped_column(String, nullable=False, default="incumbent")

    __table_args__ = (
        CheckConstraint("tier IN ('global','regional','domestic')", name="ck_bank_tier"),
        CheckConstraint(
            "connectivity IN ('swift_fileact','h2h','api','ebics','portal','none')",
            name="ck_bank_connectivity",
        ),
        CheckConstraint(
            "panel_status IN ('panel','incumbent','exit','under_review')",
            name="ck_bank_panel_status",
        ),
    )


class BankCountryCoverage(Base):
    __tablename__ = "bank_country_coverage"

    bank_id: Mapped[str] = mapped_column(ForeignKey("bank.id"), primary_key=True)
    country_iso2: Mapped[str] = mapped_column(ForeignKey("country.iso2"), primary_key=True)
    can_serve: Mapped[int] = mapped_column(Integer, nullable=False)


class Account(Base):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    bank_id: Mapped[str] = mapped_column(ForeignKey("bank.id"), nullable=False)
    # Last four digits only. A full account number must never reach this column.
    iban_masked: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    last_movement: Mapped[date | None] = mapped_column(Date)
    feed_type: Mapped[str] = mapped_column(String, nullable=False)
    feed_status: Mapped[str] = mapped_column(String, nullable=False, default="live")
    is_restricted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    restriction_note: Mapped[str | None] = mapped_column(String)
    annual_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_panel: Mapped[int | None] = mapped_column(Integer)
    score_unique: Mapped[int | None] = mapped_column(Integer)
    score_active: Mapped[int | None] = mapped_column(Integer)
    score_legal: Mapped[int | None] = mapped_column(Integer)
    disposition: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('operating','collections','payroll','tax','escrow',"
            "'investment','debt_service')",
            name="ck_account_purpose",
        ),
        CheckConstraint(
            "feed_type IN ('camt053','mt940','api','manual','none')",
            name="ck_account_feed_type",
        ),
        CheckConstraint(
            "feed_status IN ('live','stale','offline')", name="ck_account_feed_status"
        ),
        CheckConstraint(
            "disposition IS NULL OR disposition IN ('keep','migrate','close')",
            name="ck_account_disposition",
        ),
        Index("idx_account_entity", "entity_id"),
        Index("idx_account_bank", "bank_id"),
    )


class Balance(Base):
    __tablename__ = "balance"

    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    opening_native: Mapped[float] = mapped_column(Float, nullable=False)
    closing_native: Mapped[float] = mapped_column(Float, nullable=False)
    value_dated_native: Mapped[float] = mapped_column(Float, nullable=False)
    ingested_at: Mapped[str] = mapped_column(String, nullable=False)
