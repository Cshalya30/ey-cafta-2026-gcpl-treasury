"""Endpoint behaviour, scope enforcement and the persona capability matrix."""

from __future__ import annotations

import pytest

from .conftest import headers

ALL_PERSONAS = [f"P{n}" for n in range(1, 11)]


# ───────────────────────── scope is enforced on every endpoint ─────────────────────────


def test_every_endpoint_declares_the_scope_dependency():
    """PRD 9.3: no endpoint may forget the scope filter.

    This enumerates the route table rather than trusting a convention, which is
    the only version of this test that keeps working as routes are added.
    """
    from fastapi.routing import APIRoute

    from api.main import API_PREFIX, app
    from api.repositories.scope import current_scope

    def walk(routes, prefix: str = ""):
        """Recursive, carrying the mount prefix down.

        FastAPI wraps each included router in an _IncludedRouter: the real
        routes hang off `original_router` and their `path` is un-prefixed, with
        the prefix held on `include_context`. A flat pass over app.routes finds
        nothing, so both shapes are handled here and the count assertion below
        fails loudly if a future version changes the structure again.
        """
        for route in routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            context = getattr(route, "include_context", None)
            included = getattr(context, "included_router", None)
            if included is not None:
                yield from walk(included.routes, prefix + (context.prefix or ""))
            elif nested := getattr(route, "routes", None):
                yield from walk(nested, prefix)

    # The session endpoints run BEFORE a persona exists: they establish who is
    # calling. Every other endpoint must resolve scope. This exemption is
    # explicit and narrow so that adding a route cannot silently inherit it.
    exempt = {
        f"{API_PREFIX}/session",
        f"{API_PREFIX}/session/end",
    }

    checked = 0
    missing: list[str] = []
    for path, route in walk(app.routes):
        if not path.startswith(API_PREFIX) or path in exempt:
            continue
        checked += 1
        dependants = [d.call for d in route.dependant.dependencies]
        if current_scope not in dependants:
            missing.append(f"{sorted(route.methods)} {path}")

    assert checked >= 25, f"only {checked} API routes were inspected"
    assert not missing, "These endpoints do not resolve scope server-side:\n" + "\n".join(
        missing
    )


def test_missing_persona_header_is_rejected(client):
    assert client.get("/api/v1/state").status_code == 422


def test_unknown_persona_is_rejected(client):
    assert client.get("/api/v1/state", headers=headers("P42")).status_code == 422


def test_out_of_scope_entity_returns_403_not_a_filtered_200(client):
    response = client.get("/api/v1/entities/GCPL-GB", headers=headers("P5"))
    assert response.status_code == 403
    body = response.json()
    assert "outside your scope" in body["title"]
    # The message must name the real scope and must not imply non-existence.
    assert "GCPL-PL" in body["detail"]
    assert "does not exist" in body["detail"]


def test_regional_lead_sees_only_their_region(client):
    entities = client.get("/api/v1/entities", headers=headers("P4")).json()
    assert entities
    assert {e["region_id"] for e in entities} == {"REG-EMEA"}
    assert client.get("/api/v1/entities/GCPL-US", headers=headers("P4")).status_code == 403


def test_it_administrator_sees_no_amounts(client):
    assert client.get("/api/v1/entities", headers=headers("P9")).status_code == 403
    assert client.get("/api/v1/cash-leak", headers=headers("P9")).status_code == 403
    # Infrastructure remains visible: that is the job.
    assert client.get("/api/v1/accounts", headers=headers("P9")).status_code == 200
    accounts = client.get("/api/v1/accounts", headers=headers("P9")).json()
    assert all(a["balance"] is None for a in accounts)


# ───────────────────────── the persona capability matrix ─────────────────────────

PROPOSAL = {
    "kind": "intercompany_loan",
    "source_entity_id": "GCPL-GB",
    "target_entity_id": "GCPL-US",
    "amount_usd": 2_000_000.0,
    "tenor_days": 90,
    # Above the GBP safe-harbour floor: SONIA + 30bps + 300bps = 7.85%.
    # Pricing below it is a blocking ARMS_LENGTH failure, which is the point.
    "interest_rate": 0.0850,
    "rate_basis": "6M Term SONIA + 395bps",
    "justification": "Surplus and borrowing overlap in the daily position.",
}


@pytest.mark.parametrize("persona_id", ALL_PERSONAS)
def test_initiate_capability_is_enforced_server_side(client, persona_id):
    """Absence of the control in the DOM is not a pass; the API must refuse."""
    can_initiate = persona_id in {"P2", "P3"}
    response = client.post("/api/v1/proposals", json=PROPOSAL, headers=headers(persona_id))
    if can_initiate:
        assert response.status_code in {201, 422}, response.text
    else:
        assert response.status_code == 403, f"{persona_id} must not be able to initiate"


def test_front_office_dealer_cannot_approve(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL, headers=headers("P3"))
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]

    denied = client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        json={"justification": "Attempting self-approval."},
        headers=headers("P3"),
    )
    assert denied.status_code == 403


def test_lr1_blocks_a_creator_approving_their_own_proposal(client):
    """P2 may both initiate and approve in general, but never the same deal."""
    created = client.post("/api/v1/proposals", json=PROPOSAL, headers=headers("P2"))
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]

    denied = client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        json={"justification": "Self-approval attempt."},
        headers=headers("P2"),
    )
    assert denied.status_code == 403
    assert "LR1" in denied.json()["detail"]


def test_lr4_blocks_the_approver_from_settling(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL, headers=headers("P3"))
    proposal_id = created.json()["id"]

    approved = client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        json={"justification": "Within delegated mandate, all checks cleared."},
        headers=headers("P2"),
    )
    assert approved.status_code == 200, approved.text

    # P2 approved it and holds no settle capability either.
    denied = client.post(
        f"/api/v1/proposals/{proposal_id}/settle",
        json={"justification": "Attempting to settle what I approved."},
        headers=headers("P2"),
    )
    assert denied.status_code == 403

    settled = client.post(
        f"/api/v1/proposals/{proposal_id}/settle",
        json={"justification": "Confirmation matched against the counterparty advice."},
        headers=headers("P7"),
    )
    assert settled.status_code == 200
    assert settled.json()["status"] == "settled"


def test_a_failing_proposal_is_rejected_by_the_api(client):
    """The disabled submit control in the browser is not the control."""
    oversized = dict(PROPOSAL, amount_usd=9_000_000_000.0)
    response = client.post("/api/v1/proposals", json=oversized, headers=headers("P3"))
    assert response.status_code == 422
    assert "DEPLOYABLE_LIMIT" in response.json()["detail"]


def test_local_coordinator_submits_only_for_their_own_entity(client):
    payload = {
        "cycle_year": 2026,
        "cycle_week": 43,
        "lines": [{"week_offset": 0, "category": "receipts", "amount_native": 1000.0}],
        "justification": "Weekly cycle submission.",
    }
    assert client.post(
        "/api/v1/forecasts/GCPL-GB", json=payload, headers=headers("P5")
    ).status_code == 403
    assert client.post(
        "/api/v1/forecasts/GCPL-PL", json=payload, headers=headers("P5")
    ).status_code == 201


def test_only_risk_can_lint_a_workflow(client):
    assert client.post("/api/v1/workflows/W7/lint", headers=headers("P3")).status_code == 403
    assert client.post("/api/v1/workflows/W7/lint", headers=headers("P6")).status_code == 200


def test_only_treasurer_or_risk_can_run_the_scorer(client):
    body = {"persist": False}
    assert client.post("/api/v1/accounts/score", json=body, headers=headers("P5")).status_code == 403
    assert client.post("/api/v1/accounts/score", json=body, headers=headers("P6")).status_code == 200


# ───────────────────────── payload correctness ─────────────────────────


def test_group_view_is_byte_identical_to_what_the_cfo_receives(client):
    """PRD 8.9: no summarisation, no restatement, byte-for-byte."""
    import json

    cfo = client.get("/api/v1/entities/GCPL-PL", headers=headers("P1")).json()
    local = client.get("/api/v1/entities/GCPL-PL/group-view", headers=headers("P5")).json()

    assert json.dumps(local["entity"], sort_keys=True) == json.dumps(cfo, sort_keys=True)


def test_cash_leak_is_computed_not_stored(client, session):
    """Change a deposit rate in the database and the headline must move."""
    from sqlalchemy import text

    before = client.get("/api/v1/cash-leak", headers=headers("P2")).json()
    assert before["total_annualised_usd"] > 0
    assert before["pairs"]

    session.execute(text("UPDATE deposit_rate SET rate = 0.30"))
    session.commit()

    after = client.get("/api/v1/cash-leak", headers=headers("P2")).json()
    assert after["total_annualised_usd"] < before["total_annualised_usd"]


def test_cash_leak_arithmetic_reconciles(client):
    body = client.get("/api/v1/cash-leak", headers=headers("P2")).json()
    total = 0.0
    for pair in body["pairs"]:
        expected = pair["overlap_usd"] * pair["spread"]
        assert pair["annualised_leak_usd"] == pytest.approx(expected, rel=1e-4)
        total += pair["annualised_leak_usd"]
    assert body["total_annualised_usd"] == pytest.approx(total, rel=1e-6)


def test_every_aggregate_carries_a_coverage_figure(client):
    """PRD 8.11: an aggregate without a coverage figure is a lie by omission."""
    state = client.get("/api/v1/state", headers=headers("P2")).json()
    coverage = state["summary"]["coverage"]
    assert coverage["accounts_total"] > 0
    assert coverage["accounts_current"] <= coverage["accounts_total"]
    assert "of" in coverage["statement"]

    leak = client.get("/api/v1/cash-leak", headers=headers("P2")).json()
    assert leak["coverage"]["accounts_total"] > 0


def test_money_fields_always_carry_a_currency(client):
    entities = client.get("/api/v1/entities", headers=headers("P2")).json()
    for entity in entities:
        for field in ("total_cash", "restricted", "available_local",
                      "operating_buffer", "deployable_surplus"):
            money = entity["decomposition"][field]
            assert set(money) == {"native", "currency", "usd"}
            assert money["currency"]


def test_audit_verify_reports_the_tampered_sequence(client, session):
    from sqlalchemy import text

    assert client.get("/api/v1/audit/verify", headers=headers("P8")).json()["intact"] is True

    target = session.execute(
        text("SELECT seq FROM audit_event ORDER BY seq LIMIT 1 OFFSET 10")
    ).scalar_one()
    session.execute(
        text("UPDATE audit_event SET justification = 'edited' WHERE seq = :s"), {"s": target}
    )
    session.commit()

    body = client.get("/api/v1/audit/verify", headers=headers("P8")).json()
    assert body["intact"] is False
    assert body["broken_at"] == target


def test_openapi_documents_every_response_model(client):
    schema = client.get("/openapi.json").json()
    undocumented: list[str] = []
    for path, operations in schema["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in operations.items():
            ok = operation.get("responses", {}).get("200") or operation.get(
                "responses", {}
            ).get("201")
            if not ok or "content" not in ok:
                undocumented.append(f"{method.upper()} {path}")
    assert not undocumented, f"Untyped responses: {undocumented}"


def test_security_headers_are_present_on_every_response(client):
    response = client.get("/api/v1/state", headers=headers("P2"))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_errors_never_leak_a_stack_trace(client):
    response = client.get("/api/v1/entities/NO-SUCH-ENTITY", headers=headers("P2"))
    assert response.status_code in {403, 404}
    assert "Traceback" not in response.text
    assert ".py" not in response.text
