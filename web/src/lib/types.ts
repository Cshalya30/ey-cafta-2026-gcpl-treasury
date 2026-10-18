/** Wire types. These mirror api/schemas exactly; there is no `any` in src/. */

import type { Money } from './format';

export type { Money };

export type Coverage = {
  accounts_total: number;
  accounts_current: number;
  pct: number;
  statement: string;
};

export type Persona = {
  id: string;
  display_name: string;
  holder_name: string;
  office: string;
  scope_kind: 'group' | 'region' | 'entity' | 'platform';
  scope_ref: string | null;
  can_initiate: boolean;
  can_approve: boolean;
  can_settle: boolean;
  can_see_amounts: boolean;
};

export type Region = {
  id: string;
  name: string;
  hub_city: string;
  hub_lead: string;
  coverage_hours: string;
  utc_offset: number;
  mandate: string;
  entity_count: number;
};

export type GroupSummary = {
  as_of: string;
  entity_count: number;
  total_cash: Money;
  available_local: Money;
  restricted: Money;
  operating_buffer: Money;
  deployable_surplus: Money;
  drawn: Money;
  committed: Money;
  coverage: Coverage;
};

export type AppState = {
  as_of: string;
  persona: Persona;
  scope_entity_ids: string[];
  regions: Region[];
  summary: GroupSummary | null;
  currencies: string[];
  usd_to_inr: number;
  watermark: string;
  feature_flags: Record<string, boolean>;
};

export type Decomposition = {
  total_cash: Money;
  restricted: Money;
  available_local: Money;
  operating_buffer: Money;
  deployable_surplus: Money;
  note: string;
};

export type Entity = {
  id: string;
  legal_name: string;
  short_name: string;
  country_iso2: string;
  country_name: string;
  region_id: string;
  functional_ccy: string;
  erp_system: string;
  parent_id: string | null;
  ownership_pct: number;
  is_hq: boolean;
  acquired_on: string | null;
  onboard_status: 'live' | 'onboarding' | 'reporting_only' | 'not_onboarded';
  pool_status: 'eligible' | 'restricted' | 'review' | 'not_assessed';
  route: 'A' | 'B' | 'C' | 'D';
  decomposition: Decomposition;
  drawn: Money;
  committed: Money;
  headroom: Money;
  deposit_rate: number;
  all_in_rate: number | null;
  account_count: number;
  live_accounts: number;
  stale_accounts: number;
  offline_accounts: number;
  coverage_pct: number;
};

export type GroupView = { entity: Entity; generated_for: string; note: string };

export type Account = {
  id: string;
  entity_id: string;
  bank_id: string;
  bank_name: string;
  iban_masked: string;
  currency: string;
  purpose: string;
  opened_on: string;
  last_movement: string | null;
  feed_type: string;
  feed_status: 'live' | 'stale' | 'offline';
  is_restricted: boolean;
  restriction_note: string | null;
  annual_cost_usd: number;
  balance: Money | null;
  score_panel: number | null;
  score_unique: number | null;
  score_active: number | null;
  score_legal: number | null;
  score_total: number | null;
  disposition: 'keep' | 'migrate' | 'close' | null;
};

export type Bank = {
  id: string;
  name: string;
  tier: 'global' | 'regional' | 'domestic';
  swift_bic: string | null;
  connectivity: string;
  panel_status: 'panel' | 'incumbent' | 'exit' | 'under_review';
  account_count: number;
  countries_served: string[];
  limit_usd: number | null;
  utilised_usd: number | null;
};

export type CoverageMatrix = {
  countries: { iso2: string; name: string; route: string; exchange_control: string }[];
  banks: { id: string; name: string; tier: string; panel_status: string }[];
  grid: Record<string, Record<string, boolean>>;
};

export type AccountScore = {
  account_id: string;
  score_panel: number;
  score_unique: number;
  score_active: number;
  score_legal: number;
  score_total: number;
  disposition: string;
  reasons: string[];
};

export type ScoreResponse = {
  as_of: string;
  scored: number;
  persisted: number;
  method: string;
  results: AccountScore[];
};

export type Facility = {
  id: string;
  entity_id: string;
  bank_id: string;
  bank_name: string;
  kind: string;
  committed: Money;
  drawn: Money;
  headroom: Money;
  benchmark: string;
  spread_bps: number;
  all_in_rate: number;
  maturity: string;
  covenant_note: string | null;
};

export type ForecastLine = {
  week_offset: number;
  category: string;
  amount: Money;
  actual: Money | null;
  accuracy: number | null;
};

export type Forecast = {
  id: string;
  entity_id: string;
  cycle_year: number;
  cycle_week: number;
  horizon_weeks: number;
  status: 'draft' | 'submitted' | 'challenged' | 'approved';
  submitted_at: string | null;
  submitted_by: string | null;
  reviewed_by: string | null;
  lines: ForecastLine[];
  net_by_week: Money[];
  accuracy: number | null;
  owner: string;
};

export type Citation = { authority: string; reference: string; effect: string };

export type Route = {
  code: 'A' | 'B' | 'C' | 'D';
  name: string;
  scope: string;
  mechanism: string;
  binding_constraint: string;
  permits_movement: boolean;
  citations: Citation[];
};

export type NotionalPooling = {
  statement: string;
  citations: Citation[];
  gift_city_caveat: string;
  safe_harbour_note: string;
};

export type Pool = {
  id: string;
  name: string;
  kind: string;
  header_entity_id: string;
  header_bank_id: string;
  currency: string;
  route: 'A' | 'B' | 'C' | 'D';
  route_detail: Route;
  legal_cleared_by: string | null;
  tax_cleared_by: string | null;
  status: string;
  members: { entity_id: string; account_id: string; sweep_target: Money }[];
};

export type LeakPair = {
  surplus_entity: string;
  surplus_deployable: Money;
  deposit_rate: number;
  borrowing_entity: string;
  drawn: Money;
  all_in_rate: number;
  benchmark: string;
  route: string;
  overlap_usd: number;
  spread: number;
  annualised_leak_usd: number;
  detail: string;
  blocked_by: string[];
};

export type CashLeak = {
  as_of: string;
  total_annualised_usd: number;
  method: string;
  pairs: LeakPair[];
  excluded: { entity: string; reason: string; trapped_usd: number }[];
  coverage: Coverage;
};

export type Check = {
  check_no: number;
  code: string;
  result: 'OKAY' | 'WARN' | 'ERR';
  detail: string;
};

export type Economics = {
  source_deposit_rate: number;
  target_all_in_rate: number;
  spread: number;
  annual_saving_usd: number;
  period_saving_usd: number;
  safe_harbour_floor: number;
  safe_harbour_basis: string;
  safe_harbour_citation: string;
  workings: string;
};

export type Evaluation = {
  as_of: string;
  checks: Check[];
  verdict: string;
  blocking_count: number;
  warning_count: number;
  economics: Economics;
};

export type Proposal = {
  id: string;
  kind: string;
  source_entity_id: string;
  target_entity_id: string;
  amount: Money;
  tenor_days: number;
  route: string;
  interest_rate: number;
  rate_basis: string;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  settled_by: string | null;
  settled_at: string | null;
  status: string;
  checks: Check[];
  blocking_count: number;
  warning_count: number;
};

export type WorkflowNode = {
  id: string;
  label: string;
  lane: string;
  node_kind: 'start' | 'action' | 'approval' | 'system' | 'gate' | 'end';
  required_persona: string | null;
  pos_x: number;
  pos_y: number;
};

export type WorkflowEdge = {
  id: string;
  from_node: string;
  to_node: string;
  condition_label: string | null;
};

export type Violation = {
  rule_id: string;
  rule_title: string;
  severity: 'block' | 'warn';
  node_id: string | null;
  detail: string;
  detected_at: string | null;
};

export type Workflow = {
  id: string;
  name: string;
  description: string;
  version: number;
  status: string;
  node_count: number;
  violation_count: number;
  blocking_count: number;
};

export type WorkflowDetail = Workflow & {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  violations: Violation[];
  lanes: string[];
};

export type SimulationStep = {
  node_id: string;
  label: string;
  lane: string;
  node_kind: string;
  persona: string | null;
  status: 'passed' | 'blocked';
  reason: string | null;
};

export type Simulation = {
  path: SimulationStep[];
  completed: boolean;
  blocked_at: string | null;
  reason: string | null;
};

export type SodRule = {
  id: string;
  title: string;
  description: string;
  severity: 'block' | 'warn';
};

export type AuditEvent = {
  seq: number;
  ts: string;
  actor_persona: string;
  actor_name: string;
  action: string;
  object_kind: string;
  object_id: string;
  detail: string;
  justification: string | null;
  prev_hash: string;
  hash: string;
};

export type Chain = {
  intact: boolean;
  broken_at: number | null;
  checked: number;
  reason: string | null;
};

export type Kpi = {
  code: string;
  label: string;
  value: number;
  target: number;
  unit: 'pct' | 'usd' | 'count' | 'days';
  as_of: string;
  source: string;
  stale_count: number;
  direction: 'higher_is_better' | 'lower_is_better';
  on_target: boolean;
};

export type Programme = {
  waves: { id: string; name: string; start_month: number; end_month: number; description: string }[];
  gates: { id: string; month: number; criterion: string; status: string }[];
  horizon_months: number;
};

export type OnboardingItem = {
  entity_id: string;
  item_no: number;
  item: string;
  owner: string;
  due_day: number;
  status: 'open' | 'in_progress' | 'done' | 'blocked';
};

export type Exposure = {
  id: string;
  entity_id: string;
  kind: string;
  currency_pair: string | null;
  notional_usd: number;
  hedged_usd: number;
  unhedged_usd: number;
  hedge_ratio: number;
  as_of: string;
};

export type Balance = {
  account_id: string;
  entity_id: string;
  as_of: string;
  opening: Money;
  closing: Money;
  value_dated: Money;
  ingested_at: string;
  feed_status: string;
};

/** RFC 9457 problem details, as every error from this API arrives. */
export type Problem = {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string | null;
};
