"""Request and response models for every treasury resource."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .common import Coverage, Money, PersonaOut, RouteOut


# ───────────────────────── bootstrap ─────────────────────────


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    hub_city: str
    hub_lead: str
    coverage_hours: str
    utc_offset: float
    mandate: str
    entity_count: int = 0


class GroupSummary(BaseModel):
    as_of: str
    entity_count: int
    total_cash: Money
    available_local: Money
    restricted: Money
    operating_buffer: Money
    deployable_surplus: Money
    drawn: Money
    committed: Money
    coverage: Coverage


class StateOut(BaseModel):
    as_of: str
    persona: PersonaOut
    scope_entity_ids: list[str]
    regions: list[RegionOut]
    summary: GroupSummary | None = Field(
        default=None,
        description="Omitted for a platform-scoped persona, which never sees amounts.",
    )
    currencies: list[str]
    # The display-currency toggle converts through this rate, so the browser
    # never invents an FX rate of its own.
    usd_to_inr: float
    watermark: str
    feature_flags: dict[str, bool]


# ───────────────────────── entities ─────────────────────────


class EntityDecomposition(BaseModel):
    """The INV-1 and INV-2 decomposition, in the order it is stacked on screen."""

    total_cash: Money
    restricted: Money
    available_local: Money
    operating_buffer: Money
    deployable_surplus: Money
    note: str = (
        "Deployable surplus is a subset of available local cash, never an addition "
        "to it. The operating buffer is what remains after it and is never sweepable."
    )


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    legal_name: str
    short_name: str
    country_iso2: str
    country_name: str
    region_id: str
    functional_ccy: str
    erp_system: str
    parent_id: str | None
    ownership_pct: float
    is_hq: bool
    acquired_on: date | None
    onboard_status: str
    pool_status: str
    route: str

    decomposition: EntityDecomposition
    drawn: Money
    committed: Money
    headroom: Money
    deposit_rate: float
    all_in_rate: float | None

    account_count: int
    live_accounts: int
    stale_accounts: int
    offline_accounts: int
    coverage_pct: float


class GroupViewOut(BaseModel):
    """Exactly what the CFO sees about one entity. Byte-identical by construction."""

    entity: EntityOut
    generated_for: str = "group"
    note: str = (
        "This payload is produced by the same function that serves the CFO. "
        "Nothing is summarised, withheld or restated for the local view."
    )


# ───────────────────────── banking ─────────────────────────


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    bank_id: str
    bank_name: str
    iban_masked: str
    currency: str
    purpose: str
    opened_on: date
    last_movement: date | None
    feed_type: str
    feed_status: str
    is_restricted: bool
    restriction_note: str | None
    annual_cost_usd: float
    balance: Money | None
    score_panel: int | None
    score_unique: int | None
    score_active: int | None
    score_legal: int | None
    score_total: int | None
    disposition: str | None


class BankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    tier: str
    swift_bic: str | None
    connectivity: str
    panel_status: str
    account_count: int
    countries_served: list[str]
    limit_usd: float | None
    utilised_usd: float | None


class CoverageMatrixOut(BaseModel):
    countries: list[dict]
    banks: list[dict]
    grid: dict[str, dict[str, bool]]


class ScoreRequest(BaseModel):
    entity_id: str | None = None
    bank_id: str | None = None
    feed_status: str | None = None
    persist: bool = Field(
        default=False, description="Write the scores back onto the account rows."
    )


class AccountScoreOut(BaseModel):
    account_id: str
    score_panel: int
    score_unique: int
    score_active: int
    score_legal: int
    score_total: int
    disposition: str
    reasons: list[str]


class ScoreResponse(BaseModel):
    as_of: str
    scored: int
    persisted: int
    method: str
    results: list[AccountScoreOut]


# ───────────────────────── balances, funding, forecasts ─────────────────────────


class BalanceOut(BaseModel):
    account_id: str
    entity_id: str
    as_of: date
    opening: Money
    closing: Money
    value_dated: Money
    ingested_at: str
    feed_status: str


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    bank_id: str
    bank_name: str
    kind: str
    committed: Money
    drawn: Money
    headroom: Money
    benchmark: str
    spread_bps: int
    all_in_rate: float
    maturity: date
    covenant_note: str | None


class ForecastLineOut(BaseModel):
    week_offset: int
    category: str
    amount: Money
    actual: Money | None
    accuracy: float | None


class ForecastOut(BaseModel):
    id: str
    entity_id: str
    cycle_year: int
    cycle_week: int
    horizon_weeks: int
    status: str
    submitted_at: str | None
    submitted_by: str | None
    reviewed_by: str | None
    lines: list[ForecastLineOut]
    net_by_week: list[Money]
    accuracy: float | None
    owner: str


class ForecastSubmission(BaseModel):
    cycle_year: int
    cycle_week: int
    lines: list[dict] = Field(
        description="Each item is {week_offset, category, amount_native}."
    )
    justification: str = Field(min_length=4, max_length=500)


# ───────────────────────── pooling and proposals ─────────────────────────


class PoolMemberOut(BaseModel):
    entity_id: str
    account_id: str
    sweep_target: Money


class PoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: str
    header_entity_id: str
    header_bank_id: str
    currency: str
    route: str
    route_detail: RouteOut
    legal_cleared_by: str | None
    tax_cleared_by: str | None
    status: str
    members: list[PoolMemberOut]


class CheckOut(BaseModel):
    check_no: int
    code: str
    result: str
    detail: str


class ProposalCreate(BaseModel):
    kind: str = Field(pattern="^(intercompany_loan|sweep|netting|fx_hedge)$")
    source_entity_id: str = Field(min_length=1, max_length=32)
    target_entity_id: str = Field(min_length=1, max_length=32)
    amount_usd: float = Field(gt=0, le=1e12)
    tenor_days: int = Field(ge=1, le=3650)
    interest_rate: float = Field(ge=0, le=1.0)
    rate_basis: str = Field(min_length=1, max_length=120)
    rating_band: str = Field(
        default="BBB_band",
        pattern="^(AAA_to_A|BBB_band|BB_to_B|C_to_D|unrated)$",
    )
    justification: str = Field(min_length=4, max_length=500)


class ProposalOut(BaseModel):
    id: str
    kind: str
    source_entity_id: str
    target_entity_id: str
    amount: Money
    tenor_days: int
    route: str
    interest_rate: float
    rate_basis: str
    created_by: str
    created_at: str
    approved_by: str | None
    approved_at: str | None
    settled_by: str | None
    settled_at: str | None
    status: str
    checks: list[CheckOut]
    blocking_count: int
    warning_count: int


class Decision(BaseModel):
    justification: str = Field(
        min_length=4,
        max_length=500,
        description="LR7: every approval requires a recorded justification.",
    )


class EvaluateRequest(BaseModel):
    """Dry-run the nine checks without creating anything."""

    source_entity_id: str = Field(min_length=1, max_length=32)
    target_entity_id: str = Field(min_length=1, max_length=32)
    amount_usd: float = Field(gt=0, le=1e12)
    tenor_days: int = Field(ge=1, le=3650)
    interest_rate: float = Field(ge=0, le=1.0)
    kind: str = Field(default="intercompany_loan", pattern="^(intercompany_loan|sweep|netting|fx_hedge)$")
    rating_band: str = Field(default="BBB_band", pattern="^(AAA_to_A|BBB_band|BB_to_B|C_to_D|unrated)$")


class Economics(BaseModel):
    """Indicative economics, recomputed from the caller's parameters every time."""

    source_deposit_rate: float
    target_all_in_rate: float
    spread: float
    annual_saving_usd: float
    period_saving_usd: float
    safe_harbour_floor: float
    safe_harbour_basis: str
    safe_harbour_citation: str
    workings: str


class EvaluateResponse(BaseModel):
    as_of: str
    checks: list[CheckOut]
    verdict: str
    blocking_count: int
    warning_count: int
    economics: Economics


# ───────────────────────── cash leak ─────────────────────────


class LeakPairOut(BaseModel):
    surplus_entity: str
    surplus_deployable: Money
    deposit_rate: float
    borrowing_entity: str
    drawn: Money
    all_in_rate: float
    benchmark: str
    route: str
    overlap_usd: float
    spread: float
    annualised_leak_usd: float
    detail: str
    blocked_by: list[str]


class LeakExclusionOut(BaseModel):
    entity: str
    reason: str
    trapped_usd: float


class CashLeakOut(BaseModel):
    as_of: str
    total_annualised_usd: float
    method: str
    pairs: list[LeakPairOut]
    excluded: list[LeakExclusionOut]
    coverage: Coverage


# ───────────────────────── governance ─────────────────────────


class WorkflowNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    lane: str
    node_kind: str
    required_persona: str | None
    pos_x: float
    pos_y: float


class WorkflowEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_node: str
    to_node: str
    condition_label: str | None


class ViolationOut(BaseModel):
    rule_id: str
    rule_title: str
    severity: str
    node_id: str | None
    detail: str
    detected_at: str | None = None


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str
    version: int
    status: str
    node_count: int
    violation_count: int
    blocking_count: int


class WorkflowDetail(WorkflowOut):
    nodes: list[WorkflowNodeOut]
    edges: list[WorkflowEdgeOut]
    violations: list[ViolationOut]
    lanes: list[str]


class NodeMove(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    lane: str = Field(pattern="^(front|middle|back|local|regional|tax_legal|group)$")
    pos_x: float
    pos_y: float


class SimulationStepOut(BaseModel):
    node_id: str
    label: str
    lane: str
    node_kind: str
    persona: str | None
    status: str
    reason: str | None


class SimulationOut(BaseModel):
    path: list[SimulationStepOut]
    completed: bool
    blocked_at: str | None
    reason: str | None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    severity: str


# ───────────────────────── audit, KPIs, programme ─────────────────────────


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: str
    actor_persona: str
    actor_name: str
    action: str
    object_kind: str
    object_id: str
    detail: str
    justification: str | None
    prev_hash: str
    hash: str


class ChainOut(BaseModel):
    intact: bool
    broken_at: int | None
    checked: int
    reason: str | None


class KpiOut(BaseModel):
    code: str
    label: str
    value: float
    target: float
    unit: str
    as_of: str
    source: str
    stale_count: int
    direction: str
    on_target: bool


class GateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    month: int
    criterion: str
    status: str


class WaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    start_month: int
    end_month: int
    description: str


class ProgrammeOut(BaseModel):
    waves: list[WaveOut]
    gates: list[GateOut]
    horizon_months: int


class OnboardingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    item_no: int
    item: str
    owner: str
    due_day: int
    status: str


class ExposureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    kind: str
    currency_pair: str | None
    notional_usd: float
    hedged_usd: float
    unhedged_usd: float
    hedge_ratio: float
    as_of: date
