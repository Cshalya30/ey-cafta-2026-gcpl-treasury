"""Personas, segregation-of-duties rules, and the workflow graphs they are linted against."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Persona(Base):
    __tablename__ = "persona"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    holder_name: Mapped[str] = mapped_column(String, nullable=False)
    office: Mapped[str] = mapped_column(String, nullable=False)
    scope_kind: Mapped[str] = mapped_column(String, nullable=False)
    scope_ref: Mapped[str | None] = mapped_column(String)
    can_initiate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_approve: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_settle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_see_amounts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            "office IN ('front','middle','back','governance','local','regional','it','legal')",
            name="ck_persona_office",
        ),
        CheckConstraint(
            "scope_kind IN ('group','region','entity','platform')",
            name="ck_persona_scope_kind",
        ),
    )


class SodRule(Base):
    __tablename__ = "sod_rule"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    # JSON document. Format in PRD section 9.1, evaluated by services/sod.py.
    predicate: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("severity IN ('block','warn')", name="ck_sod_rule_severity"),
    )


class Workflow(Base):
    __tablename__ = "workflow"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','linted','approved','retired')", name="ck_workflow_status"
        ),
    )


class WorkflowNode(Base):
    __tablename__ = "workflow_node"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow.id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    lane: Mapped[str] = mapped_column(String, nullable=False)
    node_kind: Mapped[str] = mapped_column(String, nullable=False)
    required_persona: Mapped[str | None] = mapped_column(ForeignKey("persona.id"))
    pos_x: Mapped[float] = mapped_column(Float, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "lane IN ('front','middle','back','local','regional','tax_legal','group')",
            name="ck_workflow_node_lane",
        ),
        CheckConstraint(
            "node_kind IN ('start','action','approval','system','gate','end')",
            name="ck_workflow_node_kind",
        ),
    )


class WorkflowEdge(Base):
    __tablename__ = "workflow_edge"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow.id"), nullable=False)
    from_node: Mapped[str] = mapped_column(ForeignKey("workflow_node.id"), nullable=False)
    to_node: Mapped[str] = mapped_column(ForeignKey("workflow_node.id"), nullable=False)
    condition_label: Mapped[str | None] = mapped_column(String)


class SodViolation(Base):
    __tablename__ = "sod_violation"

    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow.id"), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("sod_rule.id"), primary_key=True)
    # Empty string rather than NULL: SQLite treats NULL primary-key parts as distinct,
    # which would let the same workflow-level violation be persisted repeatedly.
    node_id: Mapped[str] = mapped_column(String, primary_key=True, default="")
    detail: Mapped[str] = mapped_column(String, nullable=False)
    detected_at: Mapped[str] = mapped_column(String, nullable=False)
