"""Workflow Studio, the SoD linter, and the audit chain."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from ..models import (
    AuditEvent,
    SodRule,
    SodViolation,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)
from ..repositories.scope import Scope, current_scope
from ..schemas.treasury import (
    AuditEventOut,
    ChainOut,
    NodeMove,
    RuleOut,
    SimulationOut,
    SimulationStepOut,
    ViolationOut,
    WorkflowDetail,
    WorkflowEdgeOut,
    WorkflowNodeOut,
    WorkflowOut,
)
from ..services import audit as audit_service
from ..services import sod
from ..auth import Principal, guard_write

router = APIRouter(tags=["governance"])

LANES = ["local", "front", "middle", "tax_legal", "regional", "group", "back"]


def _rule_index(scope: Scope) -> dict[str, SodRule]:
    return {r.id: r for r in scope.session.execute(select(SodRule)).scalars()}


def _violations(scope: Scope, workflow_id: str) -> list[ViolationOut]:
    rules = _rule_index(scope)
    return [
        ViolationOut(
            rule_id=v.rule_id,
            rule_title=rules[v.rule_id].title if v.rule_id in rules else v.rule_id,
            severity=rules[v.rule_id].severity if v.rule_id in rules else "block",
            node_id=v.node_id or None,
            detail=v.detail,
            detected_at=v.detected_at,
        )
        for v in scope.session.execute(
            select(SodViolation)
            .where(SodViolation.workflow_id == workflow_id)
            .order_by(SodViolation.rule_id, SodViolation.node_id)
        ).scalars()
    ]


@router.get("/sod-rules", response_model=list[RuleOut], summary="LR1 to LR16")
def list_rules(scope: Scope = Depends(current_scope)) -> list[RuleOut]:
    rules = list(scope.session.execute(select(SodRule)).scalars())
    # LR2 sorts before LR10 numerically, not lexically.
    rules.sort(key=lambda r: int(r.id[2:]))
    return [RuleOut.model_validate(r) for r in rules]


@router.get("/workflows", response_model=list[WorkflowOut], summary="All fifteen workflows")
def list_workflows(scope: Scope = Depends(current_scope)) -> list[WorkflowOut]:
    node_counts = dict(
        scope.session.execute(
            select(WorkflowNode.workflow_id, func.count()).group_by(WorkflowNode.workflow_id)
        ).all()
    )
    rules = _rule_index(scope)
    violations: dict[str, list[str]] = {}
    for workflow_id, rule_id in scope.session.execute(
        select(SodViolation.workflow_id, SodViolation.rule_id)
    ).all():
        violations.setdefault(workflow_id, []).append(rule_id)

    out: list[WorkflowOut] = []
    for workflow in scope.session.execute(select(Workflow).order_by(Workflow.id)).scalars():
        found = violations.get(workflow.id, [])
        out.append(
            WorkflowOut(
                id=workflow.id,
                name=workflow.name,
                description=workflow.description,
                version=workflow.version,
                status=workflow.status,
                node_count=int(node_counts.get(workflow.id, 0)),
                violation_count=len(found),
                blocking_count=sum(
                    1 for r in found if r in rules and rules[r].severity == "block"
                ),
            )
        )
    out.sort(key=lambda w: int(w.id[1:]))
    return out


def _detail(scope: Scope, workflow: Workflow) -> WorkflowDetail:
    nodes = list(
        scope.session.execute(
            select(WorkflowNode)
            .where(WorkflowNode.workflow_id == workflow.id)
            .order_by(WorkflowNode.id)
        ).scalars()
    )
    edges = list(
        scope.session.execute(
            select(WorkflowEdge)
            .where(WorkflowEdge.workflow_id == workflow.id)
            .order_by(WorkflowEdge.id)
        ).scalars()
    )
    violations = _violations(scope, workflow.id)
    return WorkflowDetail(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        version=workflow.version,
        status=workflow.status,
        node_count=len(nodes),
        violation_count=len(violations),
        blocking_count=sum(1 for v in violations if v.severity == "block"),
        nodes=[WorkflowNodeOut.model_validate(n) for n in nodes],
        edges=[WorkflowEdgeOut.model_validate(e) for e in edges],
        violations=violations,
        lanes=LANES,
    )


@router.get(
    "/workflows/{workflow_id}", response_model=WorkflowDetail, summary="Nodes, edges, violations"
)
def get_workflow(workflow_id: str, scope: Scope = Depends(current_scope)) -> WorkflowDetail:
    workflow = scope.session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="No such workflow.")
    return _detail(scope, workflow)


@router.post(
    "/workflows/{workflow_id}/lint",
    response_model=WorkflowDetail,
    summary="Run LR1 to LR16 and persist the violations",
)
def lint(workflow_id: str, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),) -> WorkflowDetail:
    scope.require_persona_in({"P6"}, "run the segregation-of-duties linter")
    workflow = scope.session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="No such workflow.")

    violations = sod.lint_workflow(scope.session, workflow_id)
    sod.persist(scope.session, workflow_id, violations)
    workflow.status = "linted"
    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="WORKFLOW_LINTED",
        obj_kind="workflow",
        obj_id=workflow_id,
        detail=f"{len(violations)} violation(s) found across LR1 to LR16.",
        justification="Control design review.",
    )
    scope.session.commit()
    return _detail(scope, workflow)


@router.post(
    "/workflows/{workflow_id}/nodes/move",
    response_model=WorkflowDetail,
    summary="Move a node to another lane and re-lint",
)
def move_node(
    workflow_id: str, move: NodeMove, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),
) -> WorkflowDetail:
    scope.require_persona_in({"P6"}, "edit a workflow design")
    workflow = scope.session.get(Workflow, workflow_id)
    node = scope.session.get(WorkflowNode, move.node_id)
    if workflow is None or node is None or node.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="No such workflow node.")

    previous = node.lane
    node.lane = move.lane
    node.pos_x = move.pos_x
    node.pos_y = move.pos_y
    scope.session.flush()

    violations = sod.lint_workflow(scope.session, workflow_id)
    sod.persist(scope.session, workflow_id, violations)
    audit_service.append(
        scope.session,
        actor=scope.persona,
        action="WORKFLOW_NODE_MOVED",
        obj_kind="workflow",
        obj_id=workflow_id,
        detail=f"{node.label} moved from the {previous} lane to {move.lane}.",
        justification="Control design change under review.",
    )
    scope.session.commit()
    return _detail(scope, workflow)


@router.post(
    "/workflows/{workflow_id}/simulate",
    response_model=SimulationOut,
    summary="Dry-run a token and stop at the first blocking gate",
)
def simulate(workflow_id: str, scope: Scope = Depends(current_scope),
    _write: Principal = Depends(guard_write),) -> SimulationOut:
    scope.require_persona_in({"P6", "P2", "P1", "P8"}, "simulate a workflow")
    if scope.session.get(Workflow, workflow_id) is None:
        raise HTTPException(status_code=404, detail="No such workflow.")

    raw = sod.simulate(scope.session, workflow_id)
    return SimulationOut(
        path=[SimulationStepOut(**step.__dict__) for step in raw["path"]],
        completed=raw["completed"],
        blocked_at=raw["blocked_at"],
        reason=raw["reason"],
    )


# ───────────────────────── audit ─────────────────────────


@router.get("/audit", response_model=list[AuditEventOut], summary="Append-only stream")
def list_audit(
    scope: Scope = Depends(current_scope),
    object_kind: str | None = Query(default=None, max_length=32),
    object_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = Query(default=None, ge=0),
) -> list[AuditEventOut]:
    query = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
    if object_kind:
        query = query.where(AuditEvent.object_kind == object_kind)
    if object_id:
        query = query.where(AuditEvent.object_id == object_id)
    if cursor:
        query = query.where(AuditEvent.seq < cursor)
    return [AuditEventOut.model_validate(e) for e in scope.session.execute(query).scalars()]


@router.get("/audit/verify", response_model=ChainOut, summary="Walk and verify the chain")
def verify_chain(scope: Scope = Depends(current_scope)) -> ChainOut:
    result = audit_service.verify(scope.session)
    return ChainOut(
        intact=result.intact,
        broken_at=result.broken_at,
        checked=result.checked,
        reason=result.reason,
    )
