"""Pool designs, members, and the proposals that move cash between entities."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Pool(Base):
    __tablename__ = "pool"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    header_entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    header_bank_id: Mapped[str] = mapped_column(ForeignKey("bank.id"), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    legal_cleared_by: Mapped[str | None] = mapped_column(String)
    tax_cleared_by: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="design")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('physical','notional','intercompany_loan')", name="ck_pool_kind"
        ),
        CheckConstraint("route IN ('A','B','C','D')", name="ck_pool_route"),
        CheckConstraint(
            "status IN ('design','legal_review','approved','live','suspended')",
            name="ck_pool_status",
        ),
    )


class PoolMember(Base):
    __tablename__ = "pool_member"

    pool_id: Mapped[str] = mapped_column(ForeignKey("pool.id"), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    # Balance left behind in the member account after a sweep.
    sweep_target_native: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class Proposal(Base):
    __tablename__ = "proposal"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entity.id"), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Float, nullable=False)
    rate_basis: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    # LR1: must differ from created_by. Enforced in services/sod.py, not by the DB,
    # because the rule has to produce a readable violation rather than an IntegrityError.
    approved_by: Mapped[str | None] = mapped_column(String)
    approved_at: Mapped[str | None] = mapped_column(String)
    settled_by: Mapped[str | None] = mapped_column(String)
    settled_at: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('intercompany_loan','sweep','netting','fx_hedge')",
            name="ck_proposal_kind",
        ),
        CheckConstraint("route IN ('A','B','C','D')", name="ck_proposal_route"),
        CheckConstraint(
            "status IN ('draft','checks_failed','pending_auth','authorised',"
            "'rejected','settled')",
            name="ck_proposal_status",
        ),
    )


class ProposalCheck(Base):
    __tablename__ = "proposal_check"

    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposal.id"), primary_key=True)
    check_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(String, nullable=False)
    evaluated_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("result IN ('OKAY','WARN','ERR')", name="ck_proposal_check_result"),
    )
