"""The four engines: pooling checks, the SoD linter, ABAC and the audit chain."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from api.models import Persona, Proposal
from api.services import abac, audit as audit_service, metrics, pooling, routing, sod


def persona(session, persona_id: str) -> Persona:
    return session.execute(select(Persona).where(Persona.id == persona_id)).scalar_one()


# ───────────────────────── pooling: nine checks ─────────────────────────


def _draft(**overrides) -> pooling.ProposalDraft:
    base = dict(
        kind="intercompany_loan",
        source_entity_id="GCPL-GB",
        target_entity_id="GCPL-US",
        amount_usd=5_000_000.0,
        tenor_days=180,
        # Clears the GBP safe-harbour floor of 7.85%; individual tests push it
        # below deliberately where that is what they are checking.
        interest_rate=0.0850,
        rate_basis="6M Term SONIA + 395bps",
    )
    base.update(overrides)
    return pooling.ProposalDraft(**base)


def test_all_nine_checks_run_and_none_short_circuits(session):
    results = pooling.evaluate(session, _draft(), persona(session, "P3"))
    assert [r.check_no for r in results] == list(range(1, 10))
    assert [r.code for r in results] == list(pooling._CODES)
    for result in results:
        assert result.detail, f"check {result.code} must show its arithmetic"
        assert len(result.detail) > 30, f"check {result.code} detail is not usable"


def test_check1_route_blocks_route_d(session):
    results = pooling.evaluate(
        session, _draft(source_entity_id="GCPL-NG"), persona(session, "P3")
    )
    route = results[0]
    assert route.result == "ERR"
    assert "Route D" in route.detail


def test_check1_route_warns_on_india_cross_border(session):
    results = pooling.evaluate(
        session,
        _draft(source_entity_id="GCPL-IN", target_entity_id="GCPL-US", amount_usd=1_000_000.0),
        persona(session, "P3"),
    )
    assert results[0].result == "WARN"
    assert "ODI" in results[0].detail
    assert "Tax and Legal Counsel must clear this route" in results[0].detail


def test_check2_deployable_limit_blocks_oversized_request(session):
    results = pooling.evaluate(session, _draft(amount_usd=10_000_000_000.0), persona(session, "P3"))
    check = results[1]
    assert check.result == "ERR"
    assert "exceeds" in check.detail


def test_check3_protects_the_operating_buffer(session):
    """LR12 made structural: the buffer cannot be reached by a sweep."""
    financials = metrics.entity_financials(session)
    source = financials["GCPL-GB"]
    over_buffer = source.available_local_usd - source.operating_buffer_usd + 1_000_000.0

    results = pooling.evaluate(session, _draft(amount_usd=over_buffer), persona(session, "P3"))
    assert results[2].result == "ERR"
    assert "operating buffer" in results[2].detail.lower()


def test_check5_requires_the_target_to_have_drawn_debt(session):
    """Moving cash to an entity with no debt parks it; it earns no spread."""
    results = pooling.evaluate(
        session, _draft(target_entity_id="GCPL-SG"), persona(session, "P3")
    )
    assert results[4].result == "ERR"
    assert "no drawn debt" in results[4].detail


def test_check6_arms_length_floor(session):
    low = pooling.evaluate(session, _draft(interest_rate=0.0001), persona(session, "P3"))
    assert low[5].result == "ERR"
    assert "safe-harbour floor" in low[5].detail
    assert "Rule 10TD" in low[5].detail

    high = pooling.evaluate(session, _draft(interest_rate=0.3000), persona(session, "P3"))
    assert high[5].result == "OKAY"


def test_check8_data_freshness_warns_not_blocks(session):
    """LR15 is a warning. The figure still renders, with its age shown."""
    results = pooling.evaluate(
        session, _draft(source_entity_id="GCPL-IN", target_entity_id="GCPL-US"),
        persona(session, "P3"),
    )
    assert results[7].result in {"OKAY", "WARN"}
    assert results[7].result != "ERR"


def test_check9_blocks_a_persona_without_initiate(session):
    results = pooling.evaluate(session, _draft(), persona(session, "P7"))
    assert results[8].result == "ERR"
    assert "LR9" in results[8].detail


def test_check9_blocks_a_local_coordinator_acting_elsewhere(session):
    results = pooling.evaluate(session, _draft(), persona(session, "P5"))
    assert results[8].result == "ERR"


def test_verdict_reflects_blocking_checks(session):
    clean = pooling.evaluate(session, _draft(), persona(session, "P3"))
    assert pooling.verdict(clean) == "pending_auth"
    broken = pooling.evaluate(session, _draft(amount_usd=1e12), persona(session, "P3"))
    assert pooling.verdict(broken) == "checks_failed"


# ───────────────────────── safe harbour ─────────────────────────


def test_safe_harbour_inr_prices_off_mclr():
    harbour = routing.safe_harbour_floor("INR", "BBB_band", 1_000_000.0)
    expected = routing.BENCHMARK_LEVELS["SBI_1Y_MCLR"] + 325 / 10_000
    assert harbour.floor == pytest.approx(expected, abs=1e-6)
    assert "MCLR" in harbour.basis


def test_safe_harbour_fx_tiers_by_loan_size():
    small = routing.safe_harbour_floor("USD", "BBB_band", 1_000_000.0, 83.0)
    large = routing.safe_harbour_floor("USD", "BBB_band", 500_000_000.0, 83.0)
    assert large.floor >= small.floor


def test_every_rating_band_resolves():
    for band in routing.SAFE_HARBOUR_INR:
        assert routing.safe_harbour_floor("INR", band, 1.0).floor > 0
        assert routing.safe_harbour_floor("GBP", band, 1.0).floor > 0


# ───────────────────────── SoD linter ─────────────────────────


def test_lr1_fires_when_creator_approves_their_own_proposal(session):
    proposal = session.execute(select(Proposal)).scalars().first()
    proposal.approved_by = proposal.created_by
    violations = sod.lint_proposal(session, proposal, persona(session, "P3"))
    assert any(v.rule_id == "LR1" and v.blocking for v in violations)


def test_lr1_clean_when_approver_differs(session):
    proposal = session.execute(select(Proposal)).scalars().first()
    proposal.created_by, proposal.approved_by = "P3", "P2"
    proposal.settled_by = "P7"
    violations = sod.lint_proposal(session, proposal, persona(session, "P2"))
    assert not any(v.rule_id == "LR1" for v in violations)


def test_lr4_fires_when_settler_also_approved(session):
    proposal = session.execute(select(Proposal)).scalars().first()
    proposal.created_by, proposal.approved_by, proposal.settled_by = "P3", "P2", "P2"
    violations = sod.lint_proposal(session, proposal, persona(session, "P2"))
    assert any(v.rule_id == "LR4" and v.blocking for v in violations)


def test_w7_carries_a_deliberate_lr1_violation(session):
    """The seeded FX hedge workflow has a dealer approving their own deal."""
    violations = sod.lint_workflow(session, "W7")
    assert any(v.rule_id == "LR1" for v in violations)
    offending = next(v for v in violations if v.rule_id == "LR1")
    assert offending.node_id, "the offending node must be identified for highlighting"


def test_w12_carries_a_deliberate_back_office_violation(session):
    violations = sod.lint_workflow(session, "W12")
    assert {v.rule_id for v in violations} & {"LR4", "LR9"}


def test_a_clean_workflow_lints_clean(session):
    assert sod.lint_workflow(session, "W3") == []


def test_moving_a_node_into_the_wrong_lane_creates_a_violation(session):
    """Dragging the limit-setting node into Front Office must fire LR8."""
    from api.models import WorkflowNode

    node = session.execute(
        select(WorkflowNode).where(WorkflowNode.id == "W6-N2")
    ).scalar_one()
    assert "limit" in node.label.lower()

    before = {v.rule_id for v in sod.lint_workflow(session, "W6")}
    node.lane = "front"
    session.flush()
    after = {v.rule_id for v in sod.lint_workflow(session, "W6")}

    assert "LR8" not in before
    assert "LR8" in after


def test_simulation_stops_at_the_first_blocking_gate(session):
    result = sod.simulate(session, "W7")
    assert result["completed"] is False
    assert result["blocked_at"]
    assert result["reason"]
    assert result["path"][-1].status == "blocked"


def test_simulation_completes_on_a_clean_workflow(session):
    result = sod.simulate(session, "W3")
    assert result["completed"] is True
    assert result["path"][-1].node_kind == "end"


def test_all_sixteen_rules_are_present(session):
    from api.models import SodRule

    ids = {r.id for r in session.execute(select(SodRule)).scalars()}
    assert ids == {f"LR{n}" for n in range(1, 17)}


# ───────────────────────── ABAC ─────────────────────────


def test_scope_resolution_for_all_ten_personas(session):
    expected_kinds = {
        "P1": "group", "P2": "group", "P3": "group", "P4": "region", "P5": "entity",
        "P6": "group", "P7": "group", "P8": "group", "P9": "platform", "P10": "group",
    }
    all_ids = abac.all_entity_ids(session)

    for persona_id, kind in expected_kinds.items():
        p = persona(session, persona_id)
        assert p.scope_kind == kind
        visible = abac.visible_entity_ids(p, session)
        if kind == "group":
            assert visible == all_ids
        elif kind == "entity":
            assert visible == {p.scope_ref}
        elif kind == "platform":
            assert visible == set(), "IT administers infrastructure, never amounts"
        else:
            assert visible and visible < all_ids


def test_platform_persona_never_sees_amounts(session):
    assert abac.can_see_amounts(persona(session, "P9")) is False
    assert abac.can_see_amounts(persona(session, "P1")) is True


def test_require_entity_raises_outside_scope(session):
    with pytest.raises(abac.ScopeError):
        abac.require_entity(persona(session, "P5"), "GCPL-GB", session)
    abac.require_entity(persona(session, "P5"), "GCPL-PL", session)


# ───────────────────────── audit chain ─────────────────────────


def test_chain_is_intact_as_generated(session):
    result = audit_service.verify(session)
    assert result.intact
    assert result.broken_at is None
    assert result.checked > 200


def test_append_extends_the_chain(session):
    before = audit_service.verify(session)
    event = audit_service.append(
        session,
        actor=persona(session, "P2"),
        action="TEST_EVENT",
        obj_kind="entity",
        obj_id="GCPL-GB",
        detail="Appended by a test.",
        justification="Chain continuity check.",
    )
    session.flush()
    after = audit_service.verify(session)
    assert after.intact
    assert after.checked == before.checked + 1
    assert event.prev_hash != audit_service.GENESIS_HASH


def test_tampering_with_one_row_is_detected_at_that_seq(session):
    """Change one detail string; verify must name that exact sequence number."""
    target = session.execute(
        text("SELECT seq FROM audit_event ORDER BY seq LIMIT 1 OFFSET 42")
    ).scalar_one()
    session.execute(
        text("UPDATE audit_event SET detail = :d WHERE seq = :s"),
        {"d": "tampered", "s": target},
    )
    session.flush()

    result = audit_service.verify(session)
    assert result.intact is False
    assert result.broken_at == target
    assert "altered after it was written" in (result.reason or "")


def test_audit_service_exposes_no_update_or_delete():
    assert not hasattr(audit_service, "update")
    assert not hasattr(audit_service, "delete")
    assert hasattr(audit_service, "append")
