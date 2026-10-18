"""The fifteen pre-loaded workflow graphs (PRD section 8.6).

Each step is (label, lane, node_kind, required_persona, incoming_condition).
The incoming condition doubles as the recorded justification LR7 looks for.

W7 and W12 carry deliberate segregation-of-duties defects so the linter has
something real to find on first load. They are marked below; do not "fix" them.
"""

from __future__ import annotations

Step = tuple[str, str, str, str | None, str | None]

LANE_ORDER = ["local", "front", "middle", "tax_legal", "regional", "group", "back"]
LANE_HEIGHT = 140
STEP_WIDTH = 260


def layout(index: int, lane: str) -> tuple[float, float]:
    return float(index * STEP_WIDTH), float(LANE_ORDER.index(lane) * LANE_HEIGHT)


WORKFLOWS: list[dict] = [
    {
        "id": "W1",
        "name": "Daily cash position consolidation",
        "description": "Normalised bank feeds to a published group cash position, every business morning.",
        "steps": [
            ("Statement cut-off", "back", "start", None, None),
            ("Ingest camt.053 and MT940 files", "back", "system", "P9", None),
            ("Normalise and map to group categories", "back", "action", "P7", None),
            ("Flag stale and offline feeds", "middle", "system", "P6", "feed older than 24 h"),
            ("Local confirmation of unmatched balances", "local", "action", "P5", "exception raised"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Publish group cash position", "group", "end", "P2", None),
        ],
    },
    {
        "id": "W2",
        "name": "13-week forecast submission and challenge",
        "description": "Entity forecast submission, regional challenge and group approval.",
        "steps": [
            ("Cycle opens", "local", "start", None, None),
            ("Populate 13-week template", "local", "action", "P5", None),
            ("Submit forecast", "local", "action", "P5", None),
            ("Variance check against prior actuals", "middle", "system", "P6", None),
            ("Regional challenge", "regional", "approval", "P4", "variance over tolerance, reason recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Forecast approved", "group", "end", "P2", None),
        ],
    },
    {
        "id": "W3",
        "name": "Intercompany loan origination",
        "description": "Cross-border intercompany loan above the committee threshold, from proposal to authorisation.",
        "steps": [
            ("Surplus and shortfall identified", "front", "start", None, None),
            ("Create loan proposal", "front", "action", "P3", None),
            ("Nine-check verification", "middle", "system", "P6", None),
            ("Route clearance", "tax_legal", "gate", "P10", "ODI or ECB cover confirmed"),
            ("Regional approval", "regional", "approval", "P4", "within delegated mandate, reason recorded"),
            ("Committee approval", "group", "approval", "P1", "above committee threshold, reason recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Authorised", "group", "end", "P2", None),
        ],
    },
    {
        "id": "W4",
        "name": "Physical sweep execution, Route A",
        "description": "India domestic physical sweep between resident entities under documented intercompany agreements.",
        "steps": [
            ("Sweep window opens", "front", "start", None, None),
            ("Propose sweep amounts", "front", "action", "P3", None),
            ("Operating buffer protection check", "middle", "system", "P6", None),
            ("Route A documentation check", "tax_legal", "gate", "P10", "intercompany agreement on file"),
            ("Treasurer approval", "group", "approval", "P2", "within mandate, reason recorded"),
            ("Instruct the sweep", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Swept", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W5",
        "name": "Pool onboarding and route assessment",
        "description": "Assessing an entity for pool membership and recording the route classification.",
        "steps": [
            ("Candidate identified", "regional", "start", None, None),
            ("Collect entity documentation", "local", "action", "P5", None),
            ("Route assessment", "tax_legal", "gate", "P10", "route A to D determined with citation"),
            ("Risk sign-off", "middle", "approval", "P6", "limits and concentration reviewed, reason recorded"),
            ("Join pool", "front", "action", "P2", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Pool member live", "group", "end", "P2", None),
        ],
    },
    {
        "id": "W6",
        "name": "Counterparty limit setting and breach escalation",
        "description": "Risk sets limits; Front Office consumes them and may never change them.",
        "steps": [
            ("Limit review opens", "middle", "start", None, None),
            ("Set counterparty limit", "middle", "action", "P6", None),
            ("Treasurer ratification", "group", "approval", "P2", "limit rationale recorded"),
            ("Monitor utilisation", "middle", "system", "P6", None),
            ("Breach escalation", "group", "approval", "P1", "breach reason recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Limit published", "middle", "end", "P6", None),
        ],
    },
    {
        # DELIBERATE DEFECT: P3 initiates and also approves (LR1), and the
        # approval carries no recorded justification (LR7).
        "id": "W7",
        "name": "FX hedge execution",
        "description": "Hedging a transaction exposure. Known defective design, retained to demonstrate the linter.",
        "steps": [
            ("Exposure identified", "front", "start", None, None),
            ("Create hedge deal", "front", "action", "P3", None),
            ("Dealer approval", "group", "approval", "P3", None),
            ("Confirm with counterparty", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Hedge booked", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W8",
        "name": "Payment run authorisation",
        "description": "Preparing and authorising a payment file, with preparation and authorisation separated.",
        "steps": [
            ("Payment proposal received", "back", "start", None, None),
            ("Prepare payment file", "back", "action", "P7", None),
            ("Sanctions and duplicate screening", "middle", "system", "P6", None),
            ("Authorise payment", "group", "approval", "P2", "beneficiary verified, reason recorded"),
            ("Release to bank", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Paid", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W9",
        "name": "Bank account opening",
        "description": "Opening an account against a demonstrated need and a panel bank.",
        "steps": [
            ("Need raised", "local", "start", None, None),
            ("Four-test justification", "middle", "system", "P6", None),
            ("Panel bank check", "middle", "action", "P6", None),
            ("Legal and tax clearance", "tax_legal", "gate", "P10", "jurisdiction requirements confirmed"),
            ("Treasurer approval", "group", "approval", "P2", "need demonstrated, reason recorded"),
            ("Open and mandate", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Account live", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W10",
        "name": "Bank account closure and migration",
        "description": "Closing or migrating an account the scorer has dispositioned.",
        "steps": [
            ("Disposition assigned", "middle", "start", None, None),
            ("Confirm no statutory requirement", "tax_legal", "gate", "P10", "no legal necessity recorded"),
            ("Local impact confirmation", "local", "action", "P5", None),
            ("Regional approval", "regional", "approval", "P4", "migration plan recorded"),
            ("Migrate balances and mandates", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Closed", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W11",
        "name": "Month-end bank reconciliation",
        "description": "Reconciling statement balances to the ERP and clearing unmatched items.",
        "steps": [
            ("Period close opens", "back", "start", None, None),
            ("Match statements to ERP", "back", "action", "P7", None),
            ("Unmatched item review", "middle", "system", "P6", None),
            ("Local explanation", "local", "action", "P5", None),
            ("Controller sign-off", "regional", "approval", "P4", "unmatched items explained, reason recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Reconciled", "back", "end", "P7", None),
        ],
    },
    {
        # DELIBERATE DEFECT: a Back Office node creates a deal (LR9) and the same
        # Back Office holder settles what it initiated (LR4).
        "id": "W12",
        "name": "Deal settlement and confirmation",
        "description": "Settling an authorised deal. Known defective design, retained to demonstrate the linter.",
        "steps": [
            ("Authorised deal received", "back", "start", None, None),
            ("Create settlement deal record", "back", "action", "P7", None),
            ("Match confirmation", "back", "action", "P7", None),
            ("Operations approval", "back", "approval", "P7", "confirmation matched"),
            ("Settle", "back", "action", "P7", None),
            ("Write audit event", "middle", "system", "P6", None),
            ("Settled", "back", "end", "P7", None),
        ],
    },
    {
        "id": "W13",
        "name": "Exception and breach remediation",
        "description": "Any raised exception through to a recorded remediation.",
        "steps": [
            ("Exception raised", "local", "start", None, None),
            ("Triage and classify", "middle", "action", "P6", None),
            ("Assign owner", "middle", "system", "P6", None),
            ("Remediation approval", "regional", "approval", "P4", "root cause recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Closed", "middle", "end", "P6", None),
        ],
    },
    {
        "id": "W14",
        "name": "Entity onboarding Day-1 kit",
        "description": "The seven-item kit that takes an acquired entity to reporting status.",
        "steps": [
            ("Acquisition completes", "group", "start", None, None),
            ("Inventory accounts and mandates", "local", "action", "P5", None),
            ("Establish statement feed", "back", "system", "P9", None),
            ("Route assessment", "tax_legal", "gate", "P10", "route classification recorded with citation"),
            ("Agree the operating buffer", "regional", "approval", "P4", "buffer agreed in writing"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Reporting live", "group", "end", "P2", None),
        ],
    },
    {
        "id": "W15",
        "name": "TMS data migration and cutover",
        "description": "Retiring this control layer into the selected vendor TMS at month eighteen.",
        "steps": [
            ("Vendor selected", "group", "start", None, None),
            ("Extract reference and transaction data", "back", "system", "P9", None),
            ("Reconcile extract to source", "middle", "action", "P6", None),
            ("Parallel run sign-off", "regional", "approval", "P4", "parallel run variance recorded"),
            ("Committee cutover approval", "group", "approval", "P1", "cutover readiness recorded"),
            ("Write audit event", "middle", "system", "P6", None),
            ("Control layer retired", "group", "end", "P2", None),
        ],
    },
]


def expand(workflow: dict) -> tuple[list[dict], list[dict]]:
    """Turn the step list into node and edge rows."""
    nodes: list[dict] = []
    edges: list[dict] = []
    wid = workflow["id"]

    for index, (label, lane, kind, persona, _condition) in enumerate(workflow["steps"]):
        x, y = layout(index, lane)
        nodes.append(
            {
                "id": f"{wid}-N{index + 1}",
                "workflow_id": wid,
                "label": label,
                "lane": lane,
                "node_kind": kind,
                "required_persona": persona,
                "pos_x": x,
                "pos_y": y,
            }
        )

    for index in range(len(workflow["steps"]) - 1):
        condition = workflow["steps"][index + 1][4]
        edges.append(
            {
                "id": f"{wid}-E{index + 1}",
                "workflow_id": wid,
                "from_node": f"{wid}-N{index + 1}",
                "to_node": f"{wid}-N{index + 2}",
                "condition_label": condition,
            }
        )

    return nodes, edges
