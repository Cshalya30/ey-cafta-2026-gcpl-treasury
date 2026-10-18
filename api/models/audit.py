"""Append-only, hash-chained audit log.

There is deliberately no update or delete path for this table anywhere in the
codebase. The repository exposes append() and nothing else.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEvent(Base):
    __tablename__ = "audit_event"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String, nullable=False)
    actor_persona: Mapped[str] = mapped_column(ForeignKey("persona.id"), nullable=False)
    actor_name: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_kind: Mapped[str] = mapped_column(String, nullable=False)
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(String, nullable=False)
    justification: Mapped[str | None] = mapped_column(String)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (Index("idx_audit_object", "object_kind", "object_id"),)
