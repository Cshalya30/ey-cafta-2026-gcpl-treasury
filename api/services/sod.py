"""The segregation-of-duties linter, LR1 to LR16 (PRD section 9.1).

Rules are rows in sod_rule, not branches in this file. This module is the
evaluator for the predicate language and the workflow-graph checks those
predicates refer to; adding a rule means adding a row, not editing code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Persona,
    SodRule,
    SodViolation,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)

BLOCK, WARN = "block", "warn"


@dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: str
    node_id: str | None
    detail: str

    @property
    def blocking(self) -> bool:
        return self.severity == BLOCK


# ───────────────────────── predicate language ─────────────────────────


def _resolve(path: str, scope: dict[str, Any]) -> Any:
    """Resolve a '$.field' or '$.a.b' path against the evaluation scope."""
    if not isinstance(path, str) or not path.startswith("$."):
        return path
    current: Any = scope
    for part in path[2:].split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


def evaluate_assertion(assertion: dict[str, Any], scope: dict[str, Any]) -> bool:
    """True when the asserted condition holds. An unknown operator fails closed."""
    if not assertion:
        return True
    (operator, operands), = assertion.items()

    match operator:
        case "neq":
            left, right = (_resolve(o, scope) for o in operands)
            return left != right
        case "eq":
            left, right = (_resolve(o, scope) for o in operands)
            return left == right
        case "gte":
            left, right = (_resolve(o, scope) for o in operands)
            return left is not None and right is not None and float(left) >= float(right)
        case "lte":
            left, right = (_resolve(o, scope) for o in operands)
            return left is not None and right is not None and float(left) <= float(right)
        case "truthy":
            return bool(_resolve(operands if isinstance(operands, str) else operands[0], scope))
        case "falsy":
            return not bool(
                _resolve(operands if isinstance(operands, str) else operands[0], scope)
            )
        case "not_in":
            needle, haystack = operands
            resolved = _resolve(haystack, scope) or []
            return _resolve(needle, scope) not in resolved
        case "all_distinct":
            values = [_resolve(o, scope) for o in operands]
            present = [v for v in values if v is not None]
            return len(present) == len(set(present))
        case "any":
            return any(evaluate_assertion(sub, scope) for sub in operands)
        case "all":
            return all(evaluate_assertion(sub, scope) for sub in operands)
        case _:
            return False


def _format(template: str, scope: dict[str, Any]) -> str:
    try:
        return template.format(**{k: v for k, v in scope.items() if not k.startswith("_")})
    except (KeyError, IndexError, ValueError):
        return template


# ───────────────────────── proposal-scoped linting ─────────────────────────


def lint_proposal(session: Session, proposal, actor: Persona | None = None) -> list[Violation]:
    """Evaluate every rule whose predicate applies to a proposal.

    The scope carries the derived figures LR11 and LR12 compare against, so
    those rules stay data rather than becoming special cases in this function.
    """
    # Imported here: services.metrics imports nothing from this module, but
    # keeping the import local documents that the linter consumes metrics and
    # never the other way round.
    from . import metrics, routing

    financials = metrics.entity_financials(session)
    source = financials.get(proposal.source_entity_id)
    fx = metrics.FxBook(session, metrics.latest_as_of(session))
    harbour = routing.safe_harbour_floor(
        source.currency if source else "USD",
        "BBB_band",
        proposal.amount_usd,
        fx.usd_per_unit_inverse("INR") if fx.has("INR") else 83.0,
    )

    scope: dict[str, Any] = {
        "safe_harbour_floor": harbour.floor,
        "source_deployable_usd": source.deployable_surplus_usd if source else 0.0,
        "id": proposal.id,
        "kind": proposal.kind,
        "created_by": proposal.created_by,
        "approved_by": proposal.approved_by,
        "settled_by": getattr(proposal, "settled_by", None),
        "amount_usd": proposal.amount_usd,
        "interest_rate": proposal.interest_rate,
        "route": proposal.route,
        "source_entity_id": proposal.source_entity_id,
        "target_entity_id": proposal.target_entity_id,
        "actor": actor.id if actor else None,
        "actor_scope": actor.scope_ref if actor else None,
        "actor_can_initiate": bool(actor.can_initiate) if actor else False,
        "actor_can_approve": bool(actor.can_approve) if actor else False,
        "actor_can_settle": bool(actor.can_settle) if actor else False,
    }

    violations: list[Violation] = []
    for rule in session.execute(select(SodRule)).scalars():
        predicate = json.loads(rule.predicate)
        if predicate.get("applies_to") != "proposal":
            continue
        if not evaluate_assertion(predicate.get("assert", {}), scope):
            violations.append(
                Violation(
                    rule_id=rule.id,
                    severity=rule.severity,
                    node_id=None,
                    detail=_format(predicate.get("message", rule.description), scope),
                )
            )
    return violations


# ───────────────────────── workflow-scoped linting ─────────────────────────

# Which lane each capability is allowed to live in. A node in the wrong lane is
# the commonest real-world SoD defect and the one the Studio is built to surface.
LANE_CAPABILITY = {
    "front": {"initiate"},
    "middle": {"limit", "lint"},
    "back": {"settle", "confirm"},
    "regional": {"approve"},
    "group": {"approve"},
    "tax_legal": {"clear"},
    "local": {"submit"},
}


def _nodes(session: Session, workflow_id: str) -> list[WorkflowNode]:
    return list(
        session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars()
    )


def _edges(session: Session, workflow_id: str) -> list[WorkflowEdge]:
    return list(
        session.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        ).scalars()
    )


def _persona_map(session: Session) -> dict[str, Persona]:
    return {p.id: p for p in session.execute(select(Persona)).scalars()}


def lint_workflow(session: Session, workflow_id: str) -> list[Violation]:
    """Structural lint of one workflow graph against LR1 to LR16."""
    nodes = _nodes(session, workflow_id)
    edges = _edges(session, workflow_id)
    personas = _persona_map(session)
    by_id = {n.id: n for n in nodes}
    severities = {
        rule.id: rule.severity for rule in session.execute(select(SodRule)).scalars()
    }

    def sev(rule_id: str) -> str:
        return severities.get(rule_id, BLOCK)

    found: list[Violation] = []

    initiators = [n for n in nodes if n.node_kind == "action" and n.lane == "front"]
    approvals = [n for n in nodes if n.node_kind == "approval"]
    settlements = [n for n in nodes if n.lane == "back" and n.node_kind == "action"]
    gates = [n for n in nodes if n.node_kind == "gate"]

    # LR1 — a dealer cannot approve their own deal.
    initiator_personas = {n.required_persona for n in initiators if n.required_persona}
    for node in approvals:
        if node.required_persona and node.required_persona in initiator_personas:
            found.append(
                Violation(
                    "LR1",
                    sev("LR1"),
                    node.id,
                    f"{node.label}: {node.required_persona} both initiates and approves "
                    f"in this workflow. A dealer cannot approve their own deal.",
                )
            )

    # LR2 — payment preparation must be independent of payment authorisation.
    preparers = {
        n.required_persona
        for n in nodes
        if "prepar" in n.label.lower() or "payment file" in n.label.lower()
    }
    for node in approvals:
        if node.required_persona and node.required_persona in preparers - {None}:
            found.append(
                Violation(
                    "LR2",
                    sev("LR2"),
                    node.id,
                    f"{node.label}: {node.required_persona} prepares and authorises the "
                    f"same payment.",
                )
            )

    # LR3 — the limit setter cannot be the limit user.
    limit_setters = {
        n.required_persona for n in nodes if "limit" in n.label.lower() and n.lane == "middle"
    }
    for node in initiators:
        if node.required_persona and node.required_persona in limit_setters - {None}:
            found.append(
                Violation(
                    "LR3",
                    sev("LR3"),
                    node.id,
                    f"{node.label}: {node.required_persona} sets the limit it then uses.",
                )
            )

    # LR4 — settlement independent of both initiation and approval.
    approver_personas = {n.required_persona for n in approvals if n.required_persona}
    for node in settlements:
        if node.required_persona and node.required_persona in (
            initiator_personas | approver_personas
        ):
            found.append(
                Violation(
                    "LR4",
                    sev("LR4"),
                    node.id,
                    f"{node.label}: {node.required_persona} settles a movement it also "
                    f"initiated or approved.",
                )
            )

    # LR5 — a cross-border movement requires a route clearance gate before execution.
    workflow = session.get(Workflow, workflow_id)
    crosses_border = workflow is not None and (
        "cross-border" in workflow.description.lower()
        or "cross border" in workflow.description.lower()
    )
    if crosses_border and not any(n.lane == "tax_legal" for n in gates):
        found.append(
            Violation(
                "LR5",
                sev("LR5"),
                None,
                "This workflow moves cash across a border but carries no Tax and Legal "
                "route clearance gate before execution.",
            )
        )

    # LR6 — every state change writes an immutable audit event.
    if nodes and not any(
        n.node_kind == "system" and "audit" in n.label.lower() for n in nodes
    ):
        found.append(
            Violation(
                "LR6",
                sev("LR6"),
                None,
                "No audit append node. Every state change must write an immutable "
                "audit event.",
            )
        )

    # LR7 — every approval requires a recorded justification.
    for node in approvals:
        incoming = [e for e in edges if e.to_node == node.id]
        has_reason = any(e.condition_label for e in incoming) or "justif" in node.label.lower()
        if not has_reason:
            found.append(
                Violation(
                    "LR7",
                    sev("LR7"),
                    node.id,
                    f"{node.label}: approval carries no recorded justification.",
                )
            )

    # LR8 — Front Office cannot modify counterparty limits.
    for node in nodes:
        if node.lane == "front" and "limit" in node.label.lower():
            found.append(
                Violation(
                    "LR8",
                    sev("LR8"),
                    node.id,
                    f"{node.label} sits in the Front Office lane but modifies counterparty "
                    f"limits.",
                )
            )

    # LR9 — Back Office cannot create a deal.
    for node in nodes:
        if node.lane == "back" and node.node_kind == "action" and (
            "create" in node.label.lower() or "initiate" in node.label.lower()
        ):
            found.append(
                Violation(
                    "LR9",
                    sev("LR9"),
                    node.id,
                    f"{node.label}: a Back Office node creates a deal.",
                )
            )

    # LR10 — a local coordinator cannot act outside their entity.
    for node in nodes:
        persona = personas.get(node.required_persona or "")
        if persona and persona.scope_kind == "entity" and node.lane in {"group", "regional"}:
            found.append(
                Violation(
                    "LR10",
                    sev("LR10"),
                    node.id,
                    f"{node.label}: {persona.display_name} is scoped to "
                    f"{persona.scope_ref} but acts in the {node.lane} lane.",
                )
            )

    # LR11 and LR12 are proposal-state rules. They are evaluated per proposal in
    # lint_proposal and by pooling checks 6 and 3, not against the graph shape.

    # LR13 — an entity that is not route-assessed cannot join a pool.
    if any("pool" in n.label.lower() and n.node_kind == "action" for n in nodes) and not any(
        n.lane == "tax_legal" for n in nodes
    ):
        found.append(
            Violation(
                "LR13",
                sev("LR13"),
                None,
                "A pool-joining action exists with no route assessment step in the "
                "Tax and Legal lane.",
            )
        )

    # LR14 — two approvals above the committee threshold.
    if workflow is not None and "committee" in workflow.description.lower():
        if len(approvals) < 2:
            found.append(
                Violation(
                    "LR14",
                    sev("LR14"),
                    None,
                    f"This workflow crosses the committee threshold but carries "
                    f"{len(approvals)} approval step(s). Two are required.",
                )
            )

    # LR16 — an internal auditor persona may never hold a write capability.
    for node in nodes:
        persona = personas.get(node.required_persona or "")
        if persona and persona.office == "governance" and node.node_kind in {
            "action",
            "approval",
        }:
            if not (persona.can_initiate or persona.can_approve or persona.can_settle):
                found.append(
                    Violation(
                        "LR16",
                        sev("LR16"),
                        node.id,
                        f"{node.label}: {persona.display_name} is read-only and cannot "
                        f"hold a write step.",
                    )
                )

    # Orphan structure: a node no token can reach is a latent control gap.
    reachable = {n.id for n in nodes if n.node_kind == "start"}
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge.from_node in reachable and edge.to_node not in reachable:
                reachable.add(edge.to_node)
                changed = True
    for node in nodes:
        if node.id not in reachable and node.node_kind != "start":
            found.append(
                Violation(
                    "LR6",
                    WARN,
                    node.id,
                    f"{node.label} is unreachable from the start node, so its control "
                    f"never executes.",
                )
            )

    return found


def persist(session: Session, workflow_id: str, violations: list[Violation]) -> None:
    """Replace this workflow's violations with the current lint result."""
    session.query(SodViolation).filter(SodViolation.workflow_id == workflow_id).delete()
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    seen: set[tuple[str, str]] = set()
    for violation in violations:
        key = (violation.rule_id, violation.node_id or "")
        if key in seen:
            continue
        seen.add(key)
        session.add(
            SodViolation(
                workflow_id=workflow_id,
                rule_id=violation.rule_id,
                node_id=violation.node_id or "",
                detail=violation.detail,
                detected_at=stamp,
            )
        )
    session.flush()


# ───────────────────────── token simulation ─────────────────────────


@dataclass
class SimulationStep:
    node_id: str
    label: str
    lane: str
    node_kind: str
    persona: str | None
    status: str  # 'passed' | 'blocked'
    reason: str | None = None


def simulate(session: Session, workflow_id: str) -> dict:
    """Dry-run a token through the graph, stopping at the first blocking gate."""
    nodes = {n.id: n for n in _nodes(session, workflow_id)}
    edges = _edges(session, workflow_id)
    violations = lint_workflow(session, workflow_id)
    blocking_by_node: dict[str, Violation] = {
        v.node_id: v for v in violations if v.blocking and v.node_id
    }

    start = next((n for n in nodes.values() if n.node_kind == "start"), None)
    if start is None:
        return {
            "path": [],
            "completed": False,
            "blocked_at": None,
            "reason": "This workflow has no start node, so no token can enter it.",
        }

    path: list[SimulationStep] = []
    visited: set[str] = set()
    current: WorkflowNode | None = start

    while current is not None and current.id not in visited:
        visited.add(current.id)
        blocker = blocking_by_node.get(current.id)
        step = SimulationStep(
            node_id=current.id,
            label=current.label,
            lane=current.lane,
            node_kind=current.node_kind,
            persona=current.required_persona,
            status="blocked" if blocker else "passed",
            reason=blocker.detail if blocker else None,
        )
        path.append(step)

        if blocker:
            return {
                "path": path,
                "completed": False,
                "blocked_at": current.id,
                "reason": blocker.detail,
            }
        if current.node_kind == "end":
            return {"path": path, "completed": True, "blocked_at": None, "reason": None}

        outgoing = [e for e in edges if e.from_node == current.id]
        current = nodes.get(outgoing[0].to_node) if outgoing else None

    return {
        "path": path,
        "completed": False,
        "blocked_at": path[-1].node_id if path else None,
        "reason": "The token reached a node with no outgoing edge before an end node.",
    }
