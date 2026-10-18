# GCPL Treasury Command — Product Requirements Document

**Version** 2.0 (full rebuild specification)
**Owner** Chirantan Shalya
**Team** Chirantan Shalya, Narayan Jaiswal, Laavanya
**Project root** `D:\Users\Chirantan\Documents\Competitions - 5th Sem\EY - Cafta CaseComp 2026\gcpl-treasury-command`
**Repo** `github.com/Cshalya30/EY-Cafta-`
**Status** Build starts 21 October 2026, after the EY CAFTA submission closes on 20 October.

---

> **Read this first.** The 20 October submission is a 17-slide PDF, a 4-minute video and an optional Excel workbook. None of those is this application. Do not start this build before the submission is filed. This document exists so that the rebuild, if the team reaches the top ten, is fast and correct rather than improvised.

---

## 0. How to use this document

This PRD is written to be read by Claude Code inside VS Code. Appendix A covers installing and configuring it on Windows.

**Working contract for the coding agent:**

1. Each numbered section of Part 2 onwards is one **milestone**. Build one milestone at a time.
2. Before coding a milestone, run `/plan` on it and have a human approve the plan.
3. Every milestone has **acceptance criteria**. They are authoritative. Do not mark a milestone done until each criterion is verified in a real browser.
4. After any UI change, verify the affected route visually using the Playwright loop in Appendix A §6.
5. Do not edit this document. If it is ambiguous, ask before building.
6. Commit at the end of every milestone. Never bundle two milestones into one commit.

---

# PART 1 — PRODUCT

## 1. What this is

GCPL Treasury Command is **the future-state treasury operating model of Global Consumer Products Ltd, rendered executable**. It is a Phase 0 control layer and a TMS requirements specification.

It gives a CFO group-wide daily cash visibility within ninety days, on normalised bank feeds, without buying anything. It then retires into whichever vendor TMS the group selects at month four.

### 1.1 What this is not

This matters more than what it is, and every contributor must be able to say it:

- **It is not a Treasury Management System and must never be described as one.** No corporate at this scale builds its own TMS. Recommending that would be the least feasible recommendation in the field.
- It is not a payment-initiating system. It never moves money. It proposes, validates and records.
- It is not a system of record for accounting. The ERPs remain the books.
- It is not a production system. It carries synthetic demonstration data and says so on every screen.

### 1.2 Why it exists

Three jobs, in order:

1. **Prove the operating model is executable.** A slide can assert that Front, Middle and Back Office are separated. Software that rejects a dealer approving their own deal demonstrates it.
2. **Make the TMS decision with data instead of assumptions.** At month four the Treasury Committee should know the real surplus-borrowing overlap, the real spread, the real data quality per entity and the real integration cost per ERP.
3. **Give the CFO sight of the group while the TMS is being procured.** Selection to go-live runs 12 to 18 months. The CFO cannot be blind for all of it.

### 1.3 The central insight the product must express

> Whenever surplus cash sits in Entity X at a deposit rate while Entity Y borrows externally at a credit spread, the group pays the full spread on the overlapping balance for as long as the overlap lasts.

This is the **Cash Leak**. It is invisible because no single entity sees both halves. The product's single most important job is to make it visible, quantified, in one number, on first load.

---

## 2. Users and personas

Ten personas. Each is an attribute bundle, not a job title, and access is computed from attributes (see §9.3).

| # | Persona | Scope | Can see | Can do |
|---|---|---|---|---|
| P1 | CFO | Group | Everything | Approve reserved matters. Cannot execute |
| P2 | Group Treasurer | Group | Everything | Propose, approve within mandate, set limits |
| P3 | Front Office Dealer | Group, execution only | Positions, rates, limits | Create deals and pool proposals. **Cannot approve or settle** |
| P4 | Regional Lead | One region | That region plus group aggregates | Approve within delegated mandate, challenge entity forecasts |
| P5 | Local Coordinator | One entity | That entity plus the group's view of it | Submit forecasts, confirm balances, raise exceptions |
| P6 | Risk and Control Analyst | Group, read plus control actions | Everything | Set and breach-check limits, run the SoD linter. **Cannot deal** |
| P7 | Operations Specialist | Group, back office | Settlements, confirmations, reconciliations | Confirm, settle, reconcile. **Cannot initiate** |
| P8 | Internal Auditor | Group, read only | Everything including the audit chain | Verify chain integrity. **No write access at all** |
| P9 | IT Administrator | Platform | Feeds, connectivity, data health | Manage connections. **No financial data visibility** |
| P10 | Tax and Legal Counsel | Group, routing only | Entity structure, routes, restrictions | Clear or block a route. Advisory sign-off on pool proposals |

**P10 is new in v2.** The v1 prototype had no tax or legal persona, which is a credibility gap given that India routing is the hardest part of the design.

### 2.1 Design rule derived from the personas

A local coordinator who believes the centre can take their payroll float will pad their forecast. Therefore:

- The local operating buffer is **never** sweepable, and the UI must show it as structurally protected, not merely excluded.
- Every entity has a **"What the group sees about me"** view showing the exact payload the CFO sees. Byte-for-byte, no summarisation.

---

# PART 2 — ARCHITECTURE

## 3. System architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  BROWSER                                                          │
│  React 19 + TypeScript + Vite                                     │
│  ├─ Shell: register switcher, persona switcher, currency, cmd-K    │
│  ├─ CANVAS   @xyflow/react node graph, 8 lenses                   │
│  ├─ CONSOLE  estate architecture map + banking register           │
│  ├─ TERMINAL ops console, blotters, work queue, audit stream      │
│  ├─ BRIEF    CFO narrative, KPI tiles, wave tracker               │
│  └─ COCKPIT  single-entity scoped view                            │
└───────────────────────┬───────────────────────────────────────────┘
                        │  REST /api/v1  (JSON)
┌───────────────────────┴───────────────────────────────────────────┐
│  API — FastAPI (Python 3.12)                                      │
│  ├─ routers/      one per resource                                │
│  ├─ services/     pooling engine, SoD linter, ABAC, audit chain   │
│  ├─ repositories/ SQLAlchemy 2.0 data access                      │
│  └─ schemas/      Pydantic v2 request and response models         │
└───────────────────────┬───────────────────────────────────────────┘
                        │  SQLAlchemy
┌───────────────────────┴───────────────────────────────────────────┐
│  SQLite (file: data/gcpl.db)                                      │
│  WAL mode. Seeded by scripts/generate_data.py                     │
└───────────────────────────────────────────────────────────────────┘
```

### 3.1 Why these choices

| Decision | Rationale | Rejected alternative |
|---|---|---|
| **SQLite, not Postgres** | A judge must run this with two commands on their own laptop. No daemon, no container, no credentials. File-based means the demo state is reproducible and committable | Postgres: better concurrency we do not need; adds an install step that can fail live |
| **FastAPI, not Express** | The existing `generate_data.py` is Python, so the data generator and the API share a language and the domain model. Pydantic gives schema validation and OpenAPI docs for free | Node/Hono: would force a rewrite of the generator or a two-language repo |
| **React + TypeScript, not vanilla JS** | v1 is 6,248 lines of hand-rolled vanilla JS in one bundle with no type safety. Types are not optional for a financial domain with twelve entities, eleven currencies and nine constraint rules | Keeping vanilla: v1 already has three internal number contradictions that types would have caught |
| **@xyflow/react, not hand-drawn SVG** | v1 hand-computes node coordinates in `canvas_graph.js`. xyflow gives panning, zoom, minimap, auto-layout, edge routing and node selection as solved problems | Hand-rolled: 545 lines to maintain for worse behaviour |
| **TanStack Table v8** | Headless. Gives sorting, filtering, column visibility, grouping and virtualization hooks without imposing markup, which matters because the visual density is the product | AG Grid: heavy, opinionated styling, licence complexity |
| **Tailwind v4 + shadcn/ui** | Components are copied into the repo, so they are owned and editable. Aligns to the Radix 12-step colour semantics the design system uses | MUI: fights dense layouts; its defaults are comfortable-density SaaS |

### 3.2 Repository layout

```
gcpl-treasury-command/
├─ docs/
│  ├─ PRD.md                    ← this file
│  ├─ DESIGN.md                 ← design system, §11
│  └─ decisions/                ← ADRs, one per non-obvious choice
├─ api/
│  ├─ main.py                   ← FastAPI app, CORS, static mount
│  ├─ db.py                     ← engine, session, WAL pragma
│  ├─ models/                   ← SQLAlchemy ORM
│  ├─ schemas/                  ← Pydantic v2
│  ├─ routers/                  ← entities, accounts, pools, workflows, audit…
│  ├─ services/
│  │  ├─ abac.py                ← persona scope resolution
│  │  ├─ pooling.py             ← nine-constraint engine
│  │  ├─ sod.py                 ← LR1–LR16 linter
│  │  ├─ audit.py               ← SHA-256 hash chain
│  │  └─ metrics.py             ← KPI computation, Cash Leak
│  └─ tests/
├─ web/
│  ├─ src/
│  │  ├─ app/                   ← routes, providers, shell
│  │  ├─ registers/             ← canvas, console, terminal, brief, cockpit
│  │  ├─ components/            ← shared UI
│  │  ├─ features/              ← entity360, pooling, workflow, audit
│  │  ├─ lib/                   ← api client, formatters, hooks
│  │  └─ styles/                ← tokens.css, globals.css
│  └─ tests/                    ← vitest + playwright
├─ scripts/
│  └─ generate_data.py          ← deterministic synthetic seed
├─ data/
│  └─ gcpl.db                   ← generated, gitignored
├─ .claude/                     ← agents, skills, commands, settings
├─ .mcp.json                    ← Playwright MCP, project scope
├─ CLAUDE.md
└─ README.md
```

---

## 4. Data model

### 4.1 Entity-relationship summary

```
region 1──* entity 1──* account *──1 bank
                │          │
                │          └──* balance (daily snapshot)
                ├──* facility ──* drawdown
                ├──* forecast ──* forecast_line
                ├──* exposure
                └──* onboarding_item

pool 1──* pool_member ──1 entity
proposal ──1 entity(source) ──1 entity(target) ──* proposal_check
workflow 1──* workflow_node 1──* workflow_edge
sod_rule *──* workflow_node   (violations)
audit_event (append-only, hash-chained)
```

### 4.2 Schema (SQLite DDL)

Build this exactly. Column names are referenced by the API contracts in §5.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────── reference ───────────────
CREATE TABLE currency (
  code            TEXT PRIMARY KEY,              -- ISO 4217, e.g. 'INR'
  name            TEXT NOT NULL,
  minor_units     INTEGER NOT NULL DEFAULT 2,
  symbol          TEXT NOT NULL
);

CREATE TABLE fx_rate (
  as_of           DATE NOT NULL,
  base            TEXT NOT NULL REFERENCES currency(code),
  quote           TEXT NOT NULL REFERENCES currency(code),
  rate            REAL NOT NULL,                 -- 1 base = rate quote
  source          TEXT NOT NULL,                 -- e.g. 'BFIX'
  PRIMARY KEY (as_of, base, quote)
);

CREATE TABLE country (
  iso2            TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  region_id       TEXT NOT NULL REFERENCES region(id),
  exchange_control TEXT NOT NULL                 -- 'none' | 'monitored' | 'restricted'
    CHECK (exchange_control IN ('none','monitored','restricted')),
  pooling_route   TEXT NOT NULL                  -- 'A' | 'B' | 'C' | 'D'  (see §10)
    CHECK (pooling_route IN ('A','B','C','D')),
  notes           TEXT
);

-- ─────────────── org structure ───────────────
CREATE TABLE region (
  id              TEXT PRIMARY KEY,              -- 'REG-ASIA'
  name            TEXT NOT NULL,
  hub_city        TEXT NOT NULL,
  hub_lead        TEXT NOT NULL,
  coverage_hours  TEXT NOT NULL,                 -- '07:00 - 18:00 IST'
  utc_offset      REAL NOT NULL,
  mandate         TEXT NOT NULL                  -- 'delegated' | 'reserved'
    CHECK (mandate IN ('delegated','reserved'))
);

CREATE TABLE entity (
  id              TEXT PRIMARY KEY,              -- 'GCPL-IN'
  legal_name      TEXT NOT NULL,                 -- 'Global Consumer Products Ltd (India HQ)'
  short_name      TEXT NOT NULL,
  country_iso2    TEXT NOT NULL REFERENCES country(iso2),
  region_id       TEXT NOT NULL REFERENCES region(id),
  functional_ccy  TEXT NOT NULL REFERENCES currency(code),
  erp_system      TEXT NOT NULL,                 -- 'SAP S/4HANA' | 'D365' | 'Oracle' | 'NetSuite' | 'Tally'
  parent_id       TEXT REFERENCES entity(id),
  ownership_pct   REAL NOT NULL DEFAULT 100.0,
  is_hq           INTEGER NOT NULL DEFAULT 0,
  acquired_on     DATE,                          -- NULL = organic
  onboard_status  TEXT NOT NULL DEFAULT 'live'
    CHECK (onboard_status IN ('live','onboarding','reporting_only','not_onboarded')),
  pool_status     TEXT NOT NULL
    CHECK (pool_status IN ('eligible','restricted','review','not_assessed')),
  loc1_certified  INTEGER NOT NULL DEFAULT 0,    -- liquidity-off-shoring clearance
  operating_buffer_native REAL NOT NULL DEFAULT 0  -- NEVER sweepable
);

-- ─────────────── banking ───────────────
CREATE TABLE bank (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  tier            TEXT NOT NULL CHECK (tier IN ('global','regional','domestic')),
  swift_bic       TEXT,
  connectivity    TEXT NOT NULL                  -- 'swift_fileact'|'h2h'|'api'|'ebics'|'portal'|'none'
    CHECK (connectivity IN ('swift_fileact','h2h','api','ebics','portal','none')),
  panel_status    TEXT NOT NULL DEFAULT 'incumbent'
    CHECK (panel_status IN ('panel','incumbent','exit','under_review'))
);

CREATE TABLE bank_country_coverage (
  bank_id         TEXT NOT NULL REFERENCES bank(id),
  country_iso2    TEXT NOT NULL REFERENCES country(iso2),
  can_serve       INTEGER NOT NULL,              -- the EY reference-grid Yes/No
  PRIMARY KEY (bank_id, country_iso2)
);

CREATE TABLE account (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  bank_id         TEXT NOT NULL REFERENCES bank(id),
  iban_masked     TEXT NOT NULL,                 -- last 4 only, never a full number
  currency        TEXT NOT NULL REFERENCES currency(code),
  purpose         TEXT NOT NULL                  -- 'operating'|'collections'|'payroll'|'tax'|'escrow'|'investment'|'debt_service'
    CHECK (purpose IN ('operating','collections','payroll','tax','escrow','investment','debt_service')),
  opened_on       DATE NOT NULL,
  last_movement   DATE,
  feed_type       TEXT NOT NULL                  -- 'camt053'|'mt940'|'api'|'manual'|'none'
    CHECK (feed_type IN ('camt053','mt940','api','manual','none')),
  feed_status     TEXT NOT NULL DEFAULT 'live'
    CHECK (feed_status IN ('live','stale','offline')),
  is_restricted   INTEGER NOT NULL DEFAULT 0,    -- exchange control or legal block
  restriction_note TEXT,
  annual_cost_usd REAL NOT NULL DEFAULT 0,       -- from the bottom-up build, §Q-C of the annexure
  -- scoring (see §8.4)
  score_panel     INTEGER, score_unique INTEGER, score_active INTEGER, score_legal INTEGER,
  disposition     TEXT CHECK (disposition IN ('keep','migrate','close'))
);
CREATE INDEX idx_account_entity ON account(entity_id);
CREATE INDEX idx_account_bank   ON account(bank_id);

CREATE TABLE balance (
  account_id      TEXT NOT NULL REFERENCES account(id),
  as_of           DATE NOT NULL,
  opening_native  REAL NOT NULL,
  closing_native  REAL NOT NULL,
  value_dated_native REAL NOT NULL,
  ingested_at     TEXT NOT NULL,                 -- ISO 8601
  PRIMARY KEY (account_id, as_of)
);

-- ─────────────── funding ───────────────
CREATE TABLE facility (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  bank_id         TEXT NOT NULL REFERENCES bank(id),
  kind            TEXT NOT NULL CHECK (kind IN ('rcf','term','overdraft','trade','commercial_paper')),
  currency        TEXT NOT NULL REFERENCES currency(code),
  committed_native REAL NOT NULL,
  drawn_native    REAL NOT NULL,
  benchmark       TEXT NOT NULL,                 -- 'SOFR'|'EURIBOR'|'MCLR'|'SONIA'
  spread_bps      INTEGER NOT NULL,
  all_in_rate     REAL NOT NULL,                 -- decimal, e.g. 0.075
  maturity        DATE NOT NULL,
  covenant_note   TEXT
);

CREATE TABLE deposit_rate (
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  currency        TEXT NOT NULL REFERENCES currency(code),
  as_of           DATE NOT NULL,
  rate            REAL NOT NULL,                 -- decimal
  PRIMARY KEY (entity_id, currency, as_of)
);

-- ─────────────── forecasting ───────────────
CREATE TABLE forecast (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  cycle_week      INTEGER NOT NULL,              -- ISO week
  cycle_year      INTEGER NOT NULL,
  horizon_weeks   INTEGER NOT NULL DEFAULT 13,
  submitted_at    TEXT,
  submitted_by    TEXT,
  reviewed_by     TEXT,
  status          TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','challenged','approved')),
  UNIQUE (entity_id, cycle_year, cycle_week)
);

CREATE TABLE forecast_line (
  forecast_id     TEXT NOT NULL REFERENCES forecast(id),
  week_offset     INTEGER NOT NULL,              -- 0..12
  category        TEXT NOT NULL,                 -- 'receipts'|'payroll'|'suppliers'|'tax'|'capex'|'debt_service'|'other'
  amount_native   REAL NOT NULL,
  actual_native   REAL,                          -- filled after the fact, drives accuracy KPI
  PRIMARY KEY (forecast_id, week_offset, category)
);

-- ─────────────── pooling ───────────────
CREATE TABLE pool (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('physical','notional','intercompany_loan')),
  header_entity_id TEXT NOT NULL REFERENCES entity(id),
  header_bank_id  TEXT NOT NULL REFERENCES bank(id),
  currency        TEXT NOT NULL REFERENCES currency(code),
  route           TEXT NOT NULL CHECK (route IN ('A','B','C','D')),
  legal_cleared_by TEXT,
  tax_cleared_by  TEXT,
  status          TEXT NOT NULL DEFAULT 'design'
    CHECK (status IN ('design','legal_review','approved','live','suspended'))
);

CREATE TABLE pool_member (
  pool_id         TEXT NOT NULL REFERENCES pool(id),
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  account_id      TEXT NOT NULL REFERENCES account(id),
  sweep_target_native REAL NOT NULL DEFAULT 0,   -- balance left behind
  PRIMARY KEY (pool_id, account_id)
);

CREATE TABLE proposal (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('intercompany_loan','sweep','netting','fx_hedge')),
  source_entity_id TEXT NOT NULL REFERENCES entity(id),
  target_entity_id TEXT NOT NULL REFERENCES entity(id),
  amount_usd      REAL NOT NULL,
  tenor_days      INTEGER NOT NULL,
  route           TEXT NOT NULL CHECK (route IN ('A','B','C','D')),
  interest_rate   REAL NOT NULL,                 -- must clear the Rule 10TD floor, §10.4
  rate_basis      TEXT NOT NULL,                 -- 'MCLR+325bps'
  created_by      TEXT NOT NULL,
  created_at      TEXT NOT NULL,
  approved_by     TEXT,                          -- MUST differ from created_by (LR1)
  approved_at     TEXT,
  status          TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','checks_failed','pending_auth','authorised','rejected','settled'))
);

CREATE TABLE proposal_check (
  proposal_id     TEXT NOT NULL REFERENCES proposal(id),
  check_no        INTEGER NOT NULL,              -- 1..9, see §9.2
  code            TEXT NOT NULL,
  result          TEXT NOT NULL CHECK (result IN ('OKAY','WARN','ERR')),
  detail          TEXT NOT NULL,
  evaluated_at    TEXT NOT NULL,
  PRIMARY KEY (proposal_id, check_no)
);

-- ─────────────── risk ───────────────
CREATE TABLE counterparty_limit (
  bank_id         TEXT NOT NULL REFERENCES bank(id),
  limit_kind      TEXT NOT NULL CHECK (limit_kind IN ('cash','facility','derivative')),
  limit_usd       REAL NOT NULL,
  utilised_usd    REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (bank_id, limit_kind)
);

CREATE TABLE exposure (
  id              TEXT PRIMARY KEY,
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  kind            TEXT NOT NULL CHECK (kind IN ('fx_transaction','fx_translation','interest_rate','commodity')),
  currency_pair   TEXT,
  notional_usd    REAL NOT NULL,
  hedged_usd      REAL NOT NULL DEFAULT 0,
  as_of           DATE NOT NULL
);

-- ─────────────── governance ───────────────
CREATE TABLE persona (
  id              TEXT PRIMARY KEY,              -- 'P5'
  display_name    TEXT NOT NULL,
  holder_name     TEXT NOT NULL,
  office          TEXT NOT NULL CHECK (office IN ('front','middle','back','governance','local','regional','it','legal')),
  scope_kind      TEXT NOT NULL CHECK (scope_kind IN ('group','region','entity','platform')),
  scope_ref       TEXT,                          -- region.id or entity.id, NULL for group
  can_initiate    INTEGER NOT NULL DEFAULT 0,
  can_approve     INTEGER NOT NULL DEFAULT 0,
  can_settle      INTEGER NOT NULL DEFAULT 0,
  can_see_amounts INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE sod_rule (
  id              TEXT PRIMARY KEY,              -- 'LR1'
  title           TEXT NOT NULL,
  description     TEXT NOT NULL,
  severity        TEXT NOT NULL CHECK (severity IN ('block','warn')),
  predicate       TEXT NOT NULL                  -- machine-readable, see §9.1
);

CREATE TABLE workflow (
  id              TEXT PRIMARY KEY,              -- 'W1'
  name            TEXT NOT NULL,
  description     TEXT NOT NULL,
  version         INTEGER NOT NULL DEFAULT 1,
  status          TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','linted','approved','retired'))
);

CREATE TABLE workflow_node (
  id              TEXT PRIMARY KEY,
  workflow_id     TEXT NOT NULL REFERENCES workflow(id),
  label           TEXT NOT NULL,
  lane            TEXT NOT NULL CHECK (lane IN ('front','middle','back','local','regional','tax_legal','group')),
  node_kind       TEXT NOT NULL CHECK (node_kind IN ('start','action','approval','system','gate','end')),
  required_persona TEXT REFERENCES persona(id),
  pos_x           REAL NOT NULL,
  pos_y           REAL NOT NULL
);

CREATE TABLE workflow_edge (
  id              TEXT PRIMARY KEY,
  workflow_id     TEXT NOT NULL REFERENCES workflow(id),
  from_node       TEXT NOT NULL REFERENCES workflow_node(id),
  to_node         TEXT NOT NULL REFERENCES workflow_node(id),
  condition_label TEXT
);

CREATE TABLE sod_violation (
  workflow_id     TEXT NOT NULL REFERENCES workflow(id),
  rule_id         TEXT NOT NULL REFERENCES sod_rule(id),
  node_id         TEXT REFERENCES workflow_node(id),
  detail          TEXT NOT NULL,
  detected_at     TEXT NOT NULL,
  PRIMARY KEY (workflow_id, rule_id, node_id)
);

-- ─────────────── audit (append-only) ───────────────
CREATE TABLE audit_event (
  seq             INTEGER PRIMARY KEY AUTOINCREMENT,
  ts              TEXT NOT NULL,                 -- ISO 8601 UTC
  actor_persona   TEXT NOT NULL REFERENCES persona(id),
  actor_name      TEXT NOT NULL,
  action          TEXT NOT NULL,                 -- 'PROPOSAL_CREATED'
  object_kind     TEXT NOT NULL,
  object_id       TEXT NOT NULL,
  detail          TEXT NOT NULL,
  justification   TEXT,                          -- required for any state change
  prev_hash       TEXT NOT NULL,
  hash            TEXT NOT NULL                  -- SHA-256, see §9.4
);
CREATE INDEX idx_audit_object ON audit_event(object_kind, object_id);

-- ─────────────── programme ───────────────
CREATE TABLE wave (
  id              TEXT PRIMARY KEY,              -- 'W0'
  name            TEXT NOT NULL,
  start_month     INTEGER NOT NULL,
  end_month       INTEGER NOT NULL,
  description     TEXT NOT NULL
);

CREATE TABLE gate (
  id              TEXT PRIMARY KEY,              -- 'G1'
  month           INTEGER NOT NULL,
  criterion       TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','passed','failed'))
);

CREATE TABLE onboarding_item (
  entity_id       TEXT NOT NULL REFERENCES entity(id),
  item_no         INTEGER NOT NULL,              -- 1..7
  item            TEXT NOT NULL,
  owner           TEXT NOT NULL,
  due_day         INTEGER NOT NULL,              -- day 1..90
  status          TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','in_progress','done','blocked')),
  PRIMARY KEY (entity_id, item_no)
);

CREATE TABLE kpi_snapshot (
  kpi_code        TEXT NOT NULL,                 -- 'cash_visibility'
  as_of           DATE NOT NULL,
  value           REAL NOT NULL,
  target          REAL NOT NULL,
  unit            TEXT NOT NULL,                 -- 'pct'|'usd'|'count'|'days'
  PRIMARY KEY (kpi_code, as_of)
);
```

### 4.3 Invariants the database must enforce

These are the three contradictions that broke v1. Enforce them in code and assert them in tests.

| # | Invariant | Test |
|---|---|---|
| **INV-1** | For every entity: `total_cash = available_local + restricted`. `deployable_surplus` is a **subset of** `available_local`, never additive | `test_entity_balance_decomposition` |
| **INV-2** | `operating_buffer = available_local - deployable_surplus`, and `operating_buffer >= 0` always | `test_operating_buffer_nonneg` |
| **INV-3** | Cash visibility is computed from one source only: `COUNT(feed_status='live') / COUNT(*)`. **No hardcoded percentage may appear anywhere in the codebase.** | `test_no_hardcoded_visibility` greps the source for `/\d\d\.\d%/` |

> v1 displayed 93.8% in a KPI tile and 95.1% in prose on the same screen, and £22.14M against £18.5M for the same balance. Both came from hardcoded strings. Grep-based tests are the cheapest insurance against that class of defect.

---

## 5. API contracts

Base path `/api/v1`. All responses JSON. All money fields carry an explicit currency and an `_usd` sibling where cross-entity comparison applies.

### 5.1 Conventions

- **Persona header.** Every request sends `X-Persona: P5`. The API resolves scope from it (§9.3) and filters the result set server-side. **Scope is never enforced in the browser.**
- **Errors.** RFC 9457 problem details: `{ "type", "title", "status", "detail", "instance" }`.
- **Pagination.** `?limit=&cursor=`. Default limit 100, max 500.
- **Dates.** ISO 8601. All timestamps UTC with a `Z` suffix.
- **Money.** Never a float in JSON for display; send `{ "native": 44200000, "currency": "GBP", "usd": 56797000 }`.

### 5.2 Endpoints

| Method | Path | Purpose | Persona gate |
|---|---|---|---|
| `GET` | `/state` | Bootstrap: group summary, regions, as-of date, feature flags | any |
| `GET` | `/entities` | List in scope. `?region=&pool_status=&onboard_status=` | any |
| `GET` | `/entities/{id}` | Entity 360 payload, all 13 tabs | scope check |
| `GET` | `/entities/{id}/group-view` | **Exactly** what the CFO sees about this entity | any |
| `GET` | `/accounts` | `?entity=&bank=&feed_status=&disposition=` | any |
| `POST` | `/accounts/score` | Run the four-test scoring over a filter set | P2, P6 |
| `GET` | `/banks` | Panel with coverage grid | any |
| `GET` | `/banks/coverage-matrix` | Country × bank grid for the rationalisation view | any |
| `GET` | `/balances?as_of=` | Daily snapshot | any |
| `GET` | `/facilities` | Debt and headroom | any |
| `GET` | `/forecasts/{entity_id}` | 13-week forecast with actuals | scope check |
| `POST` | `/forecasts/{entity_id}` | Submit a cycle | P5 own entity only |
| `GET` | `/pools` | Pool designs and status | any |
| `GET` | `/cash-leak` | **The headline number.** Overlap, spread, annualised leak, by entity pair | any |
| `POST` | `/proposals` | Create. Runs all nine checks synchronously, returns results | `can_initiate` |
| `GET` | `/proposals/{id}` | With check results | any |
| `POST` | `/proposals/{id}/approve` | **Rejects if `approver == creator` (LR1)** | `can_approve` |
| `POST` | `/proposals/{id}/settle` | **Rejects if settler was creator or approver (LR4)** | `can_settle` |
| `GET` | `/workflows` | All 15, with lint status | any |
| `GET` | `/workflows/{id}` | Nodes, edges, violations | any |
| `POST` | `/workflows/{id}/lint` | Run LR1–LR16, persist violations | P6 |
| `POST` | `/workflows/{id}/simulate` | Token dry-run, returns the path and any blocks | P6 |
| `GET` | `/audit?object_kind=&object_id=&limit=` | Append-only stream | any |
| `GET` | `/audit/verify` | Walks the chain, returns `{ intact: bool, broken_at: seq\|null }` | any |
| `GET` | `/kpis` | All nine, current value against target | any |
| `GET` | `/waves` | Programme waves and gates | any |
| `GET` | `/entities/{id}/onboarding` | The seven-item Day-1 kit | any |

### 5.3 The one endpoint that must be perfect

`GET /cash-leak` is the product's reason to exist. Contract:

```jsonc
{
  "as_of": "2026-10-17",
  "total_annualised_usd": 1001100,
  "method": "For each (surplus entity, borrowing entity) pair sharing a poolable route, overlap = MIN(deployable_surplus_usd, drawn_facility_usd); leak = overlap × (all_in_rate − deposit_rate).",
  "pairs": [
    {
      "surplus_entity": "GCPL-UK",
      "surplus_deployable": { "native": 22137500, "currency": "GBP", "usd": 28446687 },
      "deposit_rate": 0.0045,
      "borrowing_entity": "GCPL-US",
      "drawn": { "native": 14200000, "currency": "USD", "usd": 14200000 },
      "all_in_rate": 0.0750,
      "benchmark": "SOFR + 220bps",
      "route": "B",
      "overlap_usd": 14200000,
      "spread": 0.0705,
      "annualised_leak_usd": 1001100,
      "blocked_by": []
    }
  ],
  "excluded": [
    { "entity": "GCPL-NG", "reason": "Route D: exchange control, cash not deployable", "trapped_usd": 16410000 }
  ]
}
```

**Every number in this response must be computed, never stored.** If a judge changes a deposit rate in the database and reloads, the leak must change.

---

# PART 3 — FRONTEND

## 6. Stack

| Concern | Choice | Version | Note |
|---|---|---|---|
| Framework | React | 19.x | |
| Language | TypeScript | 5.x | `strict: true`, no `any` in `src/` |
| Build | Vite | 6.x | |
| Routing | React Router | 7.x | Data router, file-free config in `app/routes.tsx` |
| Server state | TanStack Query | 5.x | All API access. No `useEffect` fetching |
| URL state | nuqs | 2.x | Filters, tabs, selected entity, lens. **Every view is deep-linkable** |
| UI state | Zustand | 5.x | Persona, register, currency only |
| Styling | Tailwind CSS | 4.x | |
| Components | shadcn/ui | current | Copied into `components/ui/` |
| Tables | TanStack Table | 8.x | Headless |
| Virtualization | virtua | current | Any list over 50 rows |
| Node graph | @xyflow/react | 12.x | Canvas register and Workflow Studio |
| Charts | visx | current | Sparklines, waterfall, gantt |
| Icons | lucide-react | current | |
| Testing | Vitest + Playwright | current | |

### 6.1 Formatting rules (non-negotiable)

Derived from the Vercel Web Interface Guidelines. These are not style preferences; they are correctness in a multi-currency product.

```ts
// lib/format.ts — the ONLY place numbers become strings.
export const money = (v: number, ccy: string, locale = 'en-IN') =>
  new Intl.NumberFormat(locale, { style: 'currency', currency: ccy,
    maximumFractionDigits: 0 }).format(v);

export const inrGrouped = (v: number) =>      // lakh / crore
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(v);

export const pct = (v: number) =>
  new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1 }).format(v);

export const date = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' }).format(new Date(iso));
```

- **Never** hardcode a currency symbol or a thousands separator. v1 did, in `data.js`.
- Every numeric column carries `font-variant-numeric: tabular-nums lining-nums`.
- Account numbers, IBANs and reference codes add `slashed-zero`.
- Brand names, currency codes and counterparty names carry `translate="no"`.

---

## 7. Information architecture

Five registers, one shell. Switching register **preserves** the active entity, date, filters and persona. That is the product's core interaction promise and it is testable.

```
/                         → redirect to /canvas
/canvas?lens=cash&entity= → CANVAS   node graph, 8 lenses
/canvas/pooling           → Pooling Workbench
/canvas/workflow/:id      → Workflow Studio
/console?tab=architecture → CONSOLE  estate map, banking register, feeds
/terminal?view=dashboard  → TERMINAL ops console, blotters, queue, audit
/brief?tab=cfo            → BRIEF    narrative, KPI tiles, wave tracker
/cockpit/:entityId        → COCKPIT  single-entity scoped view
```

### 7.1 Shell

Persistent top bar: brand, breadcrumb, register switcher, currency toggle (USD / INR / native), persona switcher, feed status chip, stale-account chip, ⌘K.

Persistent bottom ribbon: `SYNTHETIC DATA // DEMO TENANT FOR EY CAFTA 2026 // DO NOT RELY FOR LIVE TRANSFERS`. **Non-removable.** It must be present in the DOM on every route and a Playwright test asserts it.

### 7.2 The eight lenses (Canvas)

One graph, re-read eight ways. Keyboard `1`–`8`.

| # | Lens | Node colour encodes | Edge encodes | Badge |
|---|---|---|---|---|
| 1 | Cash | Deployable surplus magnitude | Ownership | Surplus / borrowing |
| 2 | 13-week forecast | Net forecast position week 4 | Ownership | Submitted / challenged |
| 3 | Funding and pooling | Pool eligibility | **Proposed and live pool flows** | Route A–D |
| 4 | Risk and exposure | Unhedged exposure ratio | Counterparty link | Limit utilisation |
| 5 | Controls and SoD | Open breach count | Approval path | Breach age |
| 6 | Data health | Feed staleness | Feed path | Stale account count |
| 7 | Banking | Count of distinct banks | Account relationship | Panel / exit |
| 8 | Service (SLA) | SLA attainment | Reporting line | Response time |

**Colour never carries quantity alone.** Each lens pairs hue with a glyph or a numeric badge (NN/g: people do not perceive colour values as ordered).

### 7.3 Entity 360

Slide-over panel, thirteen tabs: Summary · Cash and accounts · Forecast · Liquidity and pooling · Funding and facilities · Investments · Exposures and hedging · Payments and settlement · Controls and exceptions · Route assessment · Activity stream · Data health · Service and SLA.

**Route assessment replaces v1's "LOC-1 Assessment Matrix".** LOC-1 was an invented term. The tab now shows the entity's actual Route A–D classification with the regulatory citation behind it, which is defensible.

---

## 8. Feature specifications

Each is a milestone. Each has acceptance criteria the agent must verify in a browser.

### 8.0 Milestone 0 — Database, generator and API skeleton

**This milestone comes first. Nothing in the browser can be built before it exists.**

**Build:** the full schema from §4.2 as SQLAlchemy models plus an Alembic-free `init_db.py`; `scripts/generate_data.py` to the §12 specification; the FastAPI app with `/state`, `/entities`, `/accounts`, `/banks`, `/cash-leak`; the ABAC repository layer from §9.3; Pydantic schemas; the audit append service from §9.4.

**Acceptance criteria**
- `python scripts/generate_data.py --seed 42` produces `data/gcpl.db` and prints a summary: 3 regions, 12 entities, 26 banks, 81 accounts, 90 days of balances, 15 workflows, 200+ audit events.
- Running it twice with the same seed produces **byte-identical** databases.
- All five generator invariants in §12.3 assert true. The script exits non-zero if any fails.
- `GET /cash-leak` returns at least one pair with a non-zero `annualised_leak_usd`, and the arithmetic in `detail` reconciles to the figure.
- `GET /audit/verify` returns `{"intact": true}`. Corrupting one row and re-running returns that row's `seq`.
- Every endpoint filters by `X-Persona`. A test enumerates the router table and fails if any endpoint is missing the scope call.
- Requesting an out-of-scope entity returns **403**, not a filtered 200.
- OpenAPI docs render at `/docs` with every response model typed.

**Deliberate ordering note:** build the generator before the API, and the API before any UI. v1 was built UI-first against a hand-written JSON blob, which is how three mutually contradictory numbers reached the screen.

---

### 8.1 Milestone 1 — Shell and data layer

**Build:** Vite app, routing, API client, TanStack Query, persona and currency stores, top bar, watermark ribbon, ⌘K palette skeleton.

**Acceptance criteria**
- `npm run dev` serves on `localhost:5173`; `uvicorn` serves the API on `8000`; the browser loads with no console errors.
- Switching register preserves `?entity=` and the persona.
- Switching currency re-renders every visible figure with correct Intl formatting, including INR lakh/crore grouping.
- The watermark ribbon is present in the DOM on all five routes.
- `color-scheme: dark` is set on `<html>`; `<meta name="theme-color">` matches the page background.

### 8.2 Milestone 2 — Canvas and the eight lenses

**Build:** xyflow graph, hierarchical auto-layout, lens switching, node cards, minimap, isolate mode, the Cash Leak edge.

**Acceptance criteria**
- The graph renders GTC → 3 hubs → 12 entities with no overlapping nodes at 1280, 1440 and 1920 px widths.
- Keys `1`–`8` switch lens in under 100 ms with no layout shift.
- In lens 1, at least one animated edge connects a surplus entity to a borrowing entity, labelled with the annualised leak from `GET /cash-leak`.
- `Escape` clears isolate mode.
- Every node's figures match `GET /entities` exactly. A Playwright test compares the DOM against the API response.

### 8.3 Milestone 3 — Entity 360

**Acceptance criteria**
- All thirteen tabs render with real data and no empty placeholder text.
- The Summary tab satisfies INV-1 and INV-2 visibly: the decomposition sums correctly and is shown as a stacked bar.
- Switching persona to a local coordinator for another entity makes the panel inaccessible, and the API returns 403, not a filtered 200.

### 8.4 Milestone 4 — Banking register and rationalisation

**Build:** 81-account table (TanStack Table, virtualized), bank coverage matrix, the four-test scorer.

**Scoring, exactly:**

| Test | Scores 1 when |
|---|---|
| T1 Panel coverage | `bank_country_coverage.can_serve = 1` for a bank with `panel_status='panel'` in this account's country |
| T2 Unique purpose | No other account in the same entity shares `purpose` and `currency` |
| T3 Activity | `last_movement >= date('now','-90 days')` |
| T4 Legal necessity | `restriction_note` records a statutory requirement |

Disposition: 4 = `keep`; 2–3 = `migrate`; 0–1 = `close`.

**Acceptance criteria**
- The table virtualizes: the DOM holds under 60 rows with 81 records loaded.
- Sorting, filtering and column visibility are reflected in the URL and survive a reload.
- Running the scorer and changing a filter does not recompute stale results.
- Header row is frozen; the first column is frozen on horizontal scroll.

### 8.5 Milestone 5 — Pooling Workbench

**Build:** Source and target selection, parameter sliders (amount, tenor, rate), live nine-check verification, indicative economics, submit for approval.

**Acceptance criteria**
- Moving the amount slider re-evaluates all nine checks in under 150 ms.
- The economics panel recomputes from the user's parameters, never from a stored constant. Verify by changing the borrowing rate in the DB and reloading.
- A proposal that fails any `ERR` check cannot be submitted; the submit control is disabled **and** the API rejects it.
- As a Front Office Dealer, the approve control is absent **and** `POST /proposals/{id}/approve` returns 403.

### 8.6 Milestone 6 — Workflow Studio and the SoD linter

**Build:** xyflow editor with seven swimlanes, 15 pre-loaded workflows, LR1–LR16 linter, token simulation.

**Acceptance criteria**
- Dragging a node into a different lane re-runs the linter and surfaces any new violation within 300 ms.
- A workflow where the same persona both initiates and approves produces an `LR1` block, with the offending node highlighted.
- Simulation shows the token path and stops at the first blocking gate with a readable reason.

### 8.7 Milestone 7 — Terminal register

**Build:** Liquidity meters, work queue, deal/payment/reconciliation blotters, kernel log with chain verification.

**Acceptance criteria**
- Every meter's percentage is computed from the API; the grep test for hardcoded percentages passes.
- "Verify chain" walks every `audit_event` and reports intact or the first broken sequence number.
- Tampering with one row in the DB and re-verifying reports that exact `seq`.

### 8.8 Milestone 8 — Brief register

**Build:** CFO narrative, four KPI poster tiles with evidence footnotes, wave tracker, onboarding Day-1 kit.

**Acceptance criteria**
- Every KPI tile carries an as-of timestamp, a source and a stale count.
- The narrative text interpolates live values. **No number appears in prose as a literal.**
- The wave tracker shows waves overlapping, not a staircase, with the four gates at months 2, 4, 12 and 18.

### 8.9 Milestone 9 — Local Cockpit

**Acceptance criteria**
- "What the group sees about me" renders the raw `GET /entities/{id}/group-view` payload, and a test asserts it is byte-identical to what the CFO persona receives for that entity.
- The local operating buffer is shown as structurally protected, with the reason stated.

### 8.10 Milestone 10 — Accessibility, performance and demo polish

**Acceptance criteria**
- Axe reports zero critical or serious violations on all five registers.
- Every interactive element has a visible `:focus-visible` ring at 3:1 contrast or better.
- Keyboard-only traversal reaches every control. The frozen header never covers the focused element.
- Lighthouse performance 90+ on `/canvas` at 1440 px.
- First contentful paint under 1.5 s on a cold load.

---

## 8.11 States: empty, loading, error, stale

Every acceptance criterion above assumes the happy path. These four states are the normal case in treasury, not the exception, and each must be designed rather than defaulted.

| State | Where it occurs | Required treatment |
|---|---|---|
| **Loading** | Any TanStack Query in flight | Skeleton rows matching the final row height exactly, so there is no layout shift on resolve. Never a centred spinner over a table. Loading labels end in an ellipsis |
| **Empty, no data yet** | An entity with no forecast submitted for the current cycle | State what is missing, who owns it, and the action. "Week 42 forecast not submitted. Owner: Edward Thornton. [Request submission]" Never "No data" alone |
| **Empty, filtered to nothing** | A table filter matching zero rows | Distinguish from the above. Name the filters applied and offer to clear them |
| **Stale** | `feed_status='stale'`, balance over 24 h old | The figure still renders, but with an age badge and a muted treatment. **Never hide a stale number**, because hiding it makes the group look more current than it is. Pooling check 8 blocks on it separately |
| **Offline feed** | `feed_status='offline'` | Show the last known value, its as-of timestamp, and the gap in days. Mark it excluded from group aggregates and state that exclusion on the aggregate |
| **Error, request failed** | 5xx or network | Inline, in place, with a retry. Never a toast that disappears. The register must stay usable |
| **Error, forbidden** | 403 from ABAC | "This entity is outside your scope." Name the persona's actual scope. Do not imply the data does not exist |
| **Partial** | Group aggregate where some entities are stale or offline | Every aggregate carries a coverage indicator: "Group cash, 76 of 81 accounts current." An aggregate without a coverage figure is a lie by omission |

**Rule derived from v1:** the group summary tile must never show a total without stating what share of accounts it covers. v1 showed `$308.81M` with `100% RECONCILED` beside a `4 STALE` chip in the same header. Both cannot be true.

---

## 8.12 Testing specification

| Layer | Tool | What must be covered |
|---|---|---|
| **Invariants** | pytest | INV-1, INV-2, INV-3 from §4.3. These are the regression tests for the v1 defects and they run on every commit |
| **Engines** | pytest | Each of the nine pooling checks, pass and fail. Each of LR1 to LR16, violation and clean. ABAC scope resolution for all ten personas. Audit chain append, verify, and detection of a tampered row |
| **Repository** | pytest | A parametrised test over the router table asserting every endpoint applies the scope filter |
| **Contracts** | schemathesis against the OpenAPI schema | Every endpoint returns its declared model. No endpoint returns a float where money is declared |
| **Components** | Vitest + Testing Library | `lib/format.ts` across all 11 currencies including INR lakh and crore. Table sorting, filtering and URL round-trip |
| **Routes** | Playwright | One test per register asserting: loads without console errors, watermark present, register switch preserves entity and persona, deep link restores filter state |
| **Persona** | Playwright | For each of the ten personas, the controls their capability flags forbid are absent from the DOM **and** the corresponding API call returns 403. Absence from the DOM alone is not a pass |
| **Visual** | Playwright `toHaveScreenshot` | One snapshot per register at 1280, 1440 and 1920. Update deliberately, never with a blanket `--update-snapshots` |
| **Accessibility** | axe-core via Playwright | Zero critical or serious violations on all five registers |

**Coverage targets:** 90% on `api/services/`, because that is where the engines live. No target elsewhere, because a coverage number on presentation code buys nothing.

**The one test that matters most:** `test_no_hardcoded_numbers` greps `web/src/` and `api/` for percentage literals, currency symbols and thousands separators outside `lib/format.ts`. v1 shipped four contradictory figures because none of them came from the data. This test is cheap and it would have caught all four.

---

# PART 4 — ENGINES

## 9. The four engines

### 9.1 SoD rule engine (LR1–LR16)

Rules are data, not code. Each row in `sod_rule` has a machine-readable predicate evaluated against a workflow graph or a proposal state.

| ID | Rule | Severity |
|---|---|---|
| LR1 | A dealer cannot approve their own deal | block |
| LR2 | Payment preparation must be independent of payment authorisation | block |
| LR3 | The limit setter cannot be the limit user | block |
| LR4 | Settlement must be independent of both initiation and approval | block |
| LR5 | A cross-border movement requires a route clearance gate before execution | block |
| LR6 | Every state change writes an immutable audit event | block |
| LR7 | Every approval requires a recorded justification | block |
| LR8 | Front Office cannot modify counterparty limits | block |
| LR9 | Back Office cannot create a deal | block |
| LR10 | A local coordinator cannot act outside their entity | block |
| LR11 | Intercompany interest must meet or exceed the safe-harbour floor | block |
| LR12 | The local operating buffer cannot be included in a sweep | block |
| LR13 | An entity that is not route-assessed cannot join a pool | block |
| LR14 | Two approvals are required above the committee threshold | block |
| LR15 | A stale feed (over 24 h) blocks a proposal using that balance | warn |
| LR16 | An internal auditor persona may never hold a write capability | block |

**LR11 and LR12 are new in v2.** LR11 encodes the Rule 10TD transfer-pricing floor. LR12 makes the operating-buffer promise structural rather than cultural.

Predicate format (evaluated by `services/sod.py`):

```json
{
  "rule": "LR1",
  "applies_to": "proposal",
  "assert": { "neq": ["$.created_by", "$.approved_by"] },
  "message": "Proposal {id}: {created_by} cannot approve their own proposal."
}
```

### 9.2 Pooling constraint engine (nine checks)

Evaluated synchronously on `POST /proposals`. Order matters; evaluation does not short-circuit, because the user needs all failures at once.

| # | Code | Check |
|---|---|---|
| 1 | `ROUTE_CLEARED` | Both entities' countries resolve to a route that permits this movement (§10) |
| 2 | `DEPLOYABLE_LIMIT` | `amount_usd <= source.deployable_surplus_usd` |
| 3 | `LOCAL_OBLIGATIONS` | The source's operating buffer is untouched after the movement |
| 4 | `POLICY_BUFFER` | A 30-day minimum liquidity coverage threshold still holds post-movement |
| 5 | `FACILITY_CHECK` | The movement genuinely avoids a drawdown; the target has drawn debt to repay |
| 6 | `ARMS_LENGTH` | `interest_rate >= safe_harbour_floor(currency, rating, size)` — see §10.4 |
| 7 | `COUNTERPARTY_LIMIT` | Post-movement bank concentration stays within `counterparty_limit` |
| 8 | `DATA_FRESHNESS` | Both entities' balance feeds are under 24 h old |
| 9 | `SOD_CLEAR` | No blocking SoD violation for the acting persona |

Each returns `OKAY`, `WARN` or `ERR` with a human-readable `detail` naming the figures used. **A check that says only "passed" is useless; it must show its arithmetic.**

### 9.3 ABAC scope resolution

```python
def visible_entity_ids(persona: Persona, session) -> set[str]:
    if persona.scope_kind == "group":   return all_entity_ids(session)
    if persona.scope_kind == "region":  return entities_in_region(persona.scope_ref, session)
    if persona.scope_kind == "entity":  return {persona.scope_ref}
    if persona.scope_kind == "platform": return set()   # IT sees infrastructure, never amounts
```

Applied in the repository layer, not the router, so no endpoint can forget it. A test enumerates every endpoint and asserts each one filters.

### 9.4 Audit hash chain

```python
def append(session, *, actor, action, obj_kind, obj_id, detail, justification):
    prev = session.query(AuditEvent).order_by(AuditEvent.seq.desc()).first()
    prev_hash = prev.hash if prev else "0" * 64
    ts = datetime.now(timezone.utc).isoformat()
    payload = f"{prev_hash}|{ts}|{actor.id}|{action}|{obj_kind}|{obj_id}|{detail}|{justification or ''}"
    return AuditEvent(..., prev_hash=prev_hash, hash=hashlib.sha256(payload.encode()).hexdigest())
```

`GET /audit/verify` recomputes every hash from `seq=1` and reports the first mismatch. There is no update or delete path for `audit_event`; the repository exposes `append` only.

---

## 10. The India routing model

The hardest and most defensible part of the product. Each route is a data classification on `country.pooling_route`, and the UI must show the citation, not just the letter.

### 10.1 The four routes

| Route | Scope | Mechanism | Binding constraint |
|---|---|---|---|
| **A** | India domestic | Physical sweep between resident entities, same currency, documented intercompany agreements | No notional offset. Indian banks may not pay interest on current accounts |
| **B** | Offshore regional | Physical pools in Singapore and the Netherlands; optional GIFT City GRCTC header | Header account must sit with an IBU or IBC |
| **C** | India cross-border | ODI or ECB only, documented loan agreements | ODI needs prior equity **and** control; the AD bank must hold the agreement before remitting |
| **D** | Restricted | Stays local, monitored, never swept | Exchange control. Trapped cash is declared, not hidden |

### 10.2 The statement the UI must make precisely

Do not render "RBI prohibits notional pooling". It is unsupportable. Render:

> Notional pooling is not an available structure for Indian resident entities, because the enabling conditions are individually blocked.

With the three blocking citations beneath it:
- RBI Master Direction DBR.Dir.No.84/13.03.00/2015-16, s.5 — no interest on current accounts
- FEMA 1999, ss.3, 4, 6(1) — unpermitted resident-to-non-resident transfers
- Notification FEMA 3(R)/2018-RB, Schedule III — resident-to-non-resident lending confined to five enumerated cases

### 10.3 The GIFT City caveat the product must not hide

An IFSC unit is **a person resident outside India** under FEMA 339/2015-RB, reg. 3. So the Indian parent's leg into a GIFT City pool remains a cross-border transaction needing ODI or ECB cover. The IFSCA GRCTC Framework of 4 April 2025 does expressly permit "pooling of funds" (Annex II item 7), but it creates no FEMA exemption for the resident entity. Surface both facts together or the feature is a vendor pitch.

### 10.4 Safe-harbour interest floor (LR11, check 6)

```python
SAFE_HARBOUR_INR = {            # SBI 1-yr MCLR as on 1 April, plus spread (bps)
    "AAA_to_A": 175, "BBB_band": 325, "BB_to_B": 475, "C_to_D": 625, "unrated": 425,
}
REFERENCE_FX = {                # reference rate as on 30 September, plus spread
    "USD": ("6M Term SOFR", 45), "EUR": ("6M EURIBOR", 0), "GBP": ("6M Term SONIA", 30),
    "JPY": ("6M TORF", 10), "AUD": ("6M BBSW", 0), "SGD": ("6M SORA", 45),
}
```

Foreign-currency spreads tier by aggregate AE loan size. Up to INR 250 crore: +150 / +300 / +400 bps. Above: +150 / +300 / +450 / +600 bps.

> **Verify before the finale.** Rule 10TD of the Income-tax Rules 1962 applies to AY 2020-21 through AY 2026-27 under sub-rule (3B). The Income-tax Act 2025 and Rules 2026 took effect 1 April 2026 and the renumbering is unconfirmed. Cite the 1962 Rules with the sub-rule (3B) applicability note, and check the gazette before presenting.

---

## 11. Design system

Full tokens live in `docs/DESIGN.md`. This is the contract.

### 11.1 Register and density

This is an **operational** dashboard, not an analytical one: time-sensitive, continuously changing, monitored at a glance. Optimise for glanceability and action.

| Surface | Row height | Source |
|---|---|---|
| Blotters, audit stream | **24 px** | IBM Carbon `xs`, "highly dense, information fit over comfort" |
| Primary tables | **32 px** | Carbon `sm` |
| Forms, settings | 40 px | Carbon `md` |

Header rows, toolbars, batch-action bars and pagination must match the body row size.

> Carbon `md` 40 px is the generic SaaS default. Using it would make this read as a web app rather than an operations tool.

### 11.2 Colour

Base surface **#161616** (Carbon Gray 100). Near-black, not pure black.

Radix 12-step semantics:

| Steps | Role |
|---|---|
| 1–2 | App and card backgrounds |
| 3–5 | Component backgrounds: normal, hover, pressed |
| 6–8 | Borders: subtle non-interactive, subtle interactive, strong interactive and focus ring |
| 9–10 | Solid fills; 9 is the highest-chroma pure colour, 10 its hover |
| 11–12 | Low-contrast and high-contrast text |

**Dark-theme elevation uses surface lightness, not shadow.** Shadows are hard to see on dark; each layer up is one step lighter than the layer below (Atlassian).

Status mapping: green settled or within limit · amber approaching limit or pending · red breach or failed · blue informational or in flight · indigo the single action accent. Step 9 for the dot, step 3 for the row tint, step 11 for the label.

> Trap: Amber, Yellow, Sky, Mint and Lime at step 9 need **dark** text, not white. Our warning state is amber, so this applies directly.

Draw each border **once**. Overlapping alpha borders produce visible intersections, and that is the commonest visual defect in dense grids (Geist).

### 11.3 Contrast floors

| Element | Minimum |
|---|---|
| Text under 24 px | 4.5:1 |
| Text 24 px and above | 3:1 |
| Graphical elements, chart lines, status dots | **3:1** |
| Focus indicators | **3:1** |

The last two are what dashboards systematically fail. A 2 px chart line or a status dot at 2.1:1 on #161616 is non-compliant even when its label passes.

### 11.4 Typography

- Sans: **Geist Sans** or **Inter**. Mono: **Geist Mono** or **IBM Plex Mono**. All four ship the `tnum` OpenType feature; verify before substituting anything.
- Numeric columns: `font-variant-numeric: tabular-nums lining-nums`.
- Identifiers and account numbers add `slashed-zero`.
- `…` not `...`; curly quotes; non-breaking spaces in `10 MB` and `⌘ K`; `text-wrap: balance` on headings.

### 11.5 Table patterns

Design against the four NN/g data-table tasks:

1. **Finding** — readable first-column identifier, columns ordered by importance, filters with a clear active state.
2. **Comparing** — freeze header rows and the identifier column; zebra striping plus hover highlighting; easy column hide, reorder and sort.
3. **Viewing or editing one row** — **non-modal side panel**, never a modal. A modal hides the adjacent records a treasury user is comparing against.
4. **Acting** — checkbox batch actions with Select All. While batch mode is active, **disable single-row actions and row overflow menus**; exit via cancel or by deselecting all (Carbon).

Sort arrows appear on hover; only the sorted column keeps its icon. Pagination always at the bottom.

### 11.6 Platform hygiene

```css
html { color-scheme: dark; }
```
```html
<meta name="theme-color" content="#161616">
```
Native `<select>` needs explicit `background-color` and `color`, or it renders unreadable in Windows dark mode.

### 11.7 Interaction rules

- Hover, active and focus must be **more** prominent than rest, not merely different.
- Use `:focus-visible`, never `outline: none` without a replacement.
- Virtualize any list over 50 items.
- Never `transition: all`; animate `transform` and `opacity` only.
- Flex children need `min-w-0` or truncation silently fails.
- Destructive actions need a confirmation or an undo window. **Non-negotiable for proposal authorisation.**
- Every stateful view is deep-linkable. Treasury users paste views to approvers; this is a workflow requirement, not a nicety.

---

## 12. Synthetic data generator

`scripts/generate_data.py`. **Deterministic**: seeded, so the same seed produces the same database. The demo must be reproducible.

### 12.1 Required shape

| Object | Count | Constraint |
|---|---|---|
| Regions | 3 | Asia (Mumbai), Europe and Middle East (London), Americas (New York) |
| Entities | 12 | One India HQ, at least 3 acquired within 24 months, at least 2 on Route D |
| Countries | 15 | Must align to the EY reference-grid country list |
| Banks | 26 | Case states "25+". Mixed tiers and connectivity |
| Accounts | 81 | Case states "75+". At least 5 stale, at least 16 restricted |
| Balances | 90 days | Per account, with plausible seasonality |
| Facilities | 8–12 | At least one drawn at a rate above a surplus entity's deposit rate |
| Forecasts | 13 weeks | Per entity, with actuals for past weeks so accuracy is computable |
| Workflows | 15 | W1–W15, at least two with deliberate SoD violations to demonstrate the linter |
| Audit events | 200+ | Valid hash chain from genesis |

### 12.2 Naming rules

- **The India HQ is `Global Consumer Products Ltd (India HQ)`.** Never a real company name. v1 shipped with `Godrej Consumer Products Ltd (HQ)`, a real BSE/NSE-listed issuer, attached to invented financials. That is a credibility bomb and a plagiarism-rule risk.
- Bank names may be real, because bank panels are public and no invented financials attach to them.
- People's names are invented and obviously so.
- Never emit a full account number. `iban_masked` holds the last four digits only.

### 12.3 Generator invariants (assert, do not hope)

```python
assert abs(total_cash - (available_local + restricted)) < 0.01      # INV-1
assert deployable_surplus <= available_local                        # INV-1
assert operating_buffer == available_local - deployable_surplus >= 0 # INV-2
assert any(leak_pairs), "dataset must contain at least one Cash Leak pair"
assert verify_audit_chain(), "generated audit chain must be intact"
```

---

## 13. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | FCP < 1.5 s cold. Lens switch < 100 ms. Nine-check evaluation < 150 ms. Any table over 50 rows virtualized |
| Accessibility | Zero critical or serious Axe violations. Full keyboard traversal. 3:1 on focus rings and graphical elements |
| Browser support | Current Chrome, Edge, Safari, Firefox. No IE, no polyfills |
| Responsive | Usable at 1280 px and above. **A treasury grid breaks at 1280, not at mobile width**, so test 1280, 1440 and 1920 |
| Security | ABAC enforced server-side only. No secrets in the repo. No real account numbers. No PII |
| Offline | The app must run with no network beyond localhost. All fonts and assets self-hosted |
| Reproducibility | `python scripts/generate_data.py --seed 42` always yields an identical database |
| Repo hygiene | **No absolute local paths in any committed file.** v1 shipped `/Users/<name>/.gemini/antigravity/scratch/...` in both `README.md` and `generate_data.py` |

---

# PART 5 — APPENDICES

## Appendix A — Claude Code in VS Code on Windows

Verified against the official documentation on 17 October 2026. Items marked **UNVERIFIED** need a test on your machine.

### A.1 Prerequisites

| Item | Requirement |
|---|---|
| OS | Windows 10 1809+ or Windows 11. 4 GB+ RAM |
| Account | Pro, Max, Team or Enterprise. The free plan has no Claude Code access |
| Node.js | Not needed for the native installer. Needed for `npm` and for the Playwright MCP server, which runs via `npx`. Use current LTS |
| Git for Windows | Recommended. Gives Claude the Bash tool; without it Claude uses PowerShell |
| Sandboxing | Not supported on native Windows. Available in WSL 2 |

Use **native Windows**, not WSL, because this project lives on the Windows filesystem and is edited in Windows VS Code.

### A.2 Install

Open **PowerShell** (not CMD):

```powershell
irm https://claude.ai/install.ps1 | iex
```

Alternative: `winget install Anthropic.ClaudeCode` (does not auto-update; use `winget upgrade`).

Close all terminals, open a new PowerShell, then:

```powershell
claude --version
claude doctor
```

If `claude is not recognized`:

```powershell
Test-Path "$env:USERPROFILE\.local\bin\claude.exe"
$p = [Environment]::GetEnvironmentVariable('PATH','User')
[Environment]::SetEnvironmentVariable('PATH', "$p;$env:USERPROFILE\.local\bin", 'User')
```

Open a new terminal. If you use the VS Code terminal, restart VS Code too, because its terminal inherits the editor's PATH.

### A.3 Open the project

```powershell
cd "D:\Users\Chirantan\Documents\Competitions - 5th Sem\EY - Cafta CaseComp 2026\gcpl-treasury-command"
claude
```

Follow the browser login prompt.

**VS Code extension:** `Ctrl+Shift+X`, search "Claude Code", Install. Requires VS Code 1.94.0+. The extension bundles its own CLI copy for its chat panel and does **not** put `claude` on your PATH; §A.2 does that. MCP configuration is shared between the two.

Open the folder with **File → Open Folder**, select `gcpl-treasury-command`, and **accept the workspace trust prompt**. Without trust, project-scoped MCP servers stay "Pending approval".

Open Claude via the spark icon, the status-bar item, `Ctrl+Shift+P` → "Claude Code: Open in New Tab", or `Ctrl+Esc`.

> **Windows path caveat (UNVERIFIED).** Your path contains spaces in `Competitions - 5th Sem` and `EY - Cafta CaseComp 2026`, and sits on `D:`. The docs do not address either. Always quote the path in PowerShell. Keep every file Claude imports inside the project folder, whose own name has no spaces. In your first session, ask Claude to run `Get-Location` and `git status` to confirm the working directory. Claude Code's own config lives under `%USERPROFILE%`, so the D: location affects only the working directory.

### A.4 Project setup

```powershell
New-Item -ItemType Directory -Force docs | Out-Null
Copy-Item "<path to PRD.md>" docs\PRD.md
git init
git add -A
git commit -m "docs: add PRD"
git tag baseline
```

A PRD inside the repo persists across sessions, survives `/clear`, is versioned and can be re-read on demand. A PRD pasted into a prompt is lost on `/clear` and costs tokens every time.

Then run `/init` to generate a starter `CLAUDE.md`. For the interactive version set `$env:CLAUDE_CODE_NEW_INIT = "1"` first. Edit later with `/memory`.

### A.5 CLAUDE.md

Loaded at session start. Claude treats it as context, not enforced configuration, so keep it short and specific. Hard rules belong in permissions. Target under 200 lines.

| File | Path | Scope | Commit |
|---|---|---|---|
| User | `%USERPROFILE%\.claude\CLAUDE.md` | All your projects | No |
| Project | `<project>\CLAUDE.md` | Team | Yes |
| Local | `<project>\CLAUDE.local.md` | You, this project | No, gitignore it |

Write this one:

```markdown
# GCPL Treasury Command

## Source of truth
- Product spec: docs/PRD.md. Before coding a feature, read the section it names.
- Do not edit docs/PRD.md. If it is ambiguous, ask before building.

## Commands
- API: cd api && uvicorn main:app --reload --port 8000
- Web: cd web && npm run dev          (http://localhost:5173)
- Seed: python scripts/generate_data.py --seed 42
- Lint: cd web && npm run lint
- Test: cd web && npm test ; cd api && pytest

## Working rules
- One PRD milestone per session. Commit after each.
- TypeScript strict. No `any` in src/.
- All numbers formatted through lib/format.ts. Never hardcode a currency symbol or a percentage.
- ABAC is enforced server-side only. Never filter by persona in the browser.
- After any UI change, verify the route with playwright-cli and compare against the milestone's acceptance criteria.
```

> **Do not `@`-import the PRD into CLAUDE.md.** Imports load into every session and will not reduce context. Point at it instead ("read docs/PRD.md section 8.4"). Paths with spaces also need backslash escaping in imports, and quoted paths are not imported at all.

### A.6 Plan mode and permissions

**Plan mode:** `Shift+Tab` until the indicator reads "plan mode on", or `claude --permission-mode plan`, or `/plan <task>`. Claude reads and writes a plan; edits stay blocked until you approve. `Ctrl+G` opens the plan in your editor so you can change it first. For milestone 1, choose "manually approve edits".

**Modes:** `default` (reads only) · `acceptEdits` (reads plus edits in the working directory) · `plan` · `auto` (classifier-reviewed; availability varies) · `dontAsk` · `bypassPermissions` (isolated containers only). `Shift+Tab` cycles the first three.

**`.claude/settings.json`** — commit this. Strict JSON: no comments, no trailing commas. Evaluation order is deny, then ask, then allow; first match wins, and an allow rule cannot carve an exception out of a deny.

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(npm install)",
      "Bash(npm run dev)",
      "Bash(npm run build)",
      "Bash(npm run lint)",
      "Bash(npm test *)",
      "Bash(pytest *)",
      "Bash(python scripts/generate_data.py *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git log *)",
      "Bash(playwright-cli *)",
      "mcp__playwright__*"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Bash(git push *)",
      "Bash(curl *)",
      "Bash(wget *)"
    ]
  }
}
```

Personal rules go in `.claude/settings.local.json`, gitignored.

> The VS Code extension does **not** read project settings for its starting mode. Set `claudeCode.initialPermissionMode` in VS Code user settings instead.

**Never auto-allow:** `Bash(*)`, `Bash(npx *)`, `Bash(node *)`, `Bash(python *)` — the wildcard matches any arguments, which is arbitrary code execution. Also `curl`, `wget`, `WebFetch(domain:*)`, `git push`, any deploy CLI, reading `.env`, and `--dangerously-skip-permissions`.

### A.7 MCP servers

| Scope | Flag | Stored in | Shared via git |
|---|---|---|---|
| local (default) | `--scope local` | `~/.claude.json` | No |
| project | `--scope project` | `.mcp.json` in the repo root | **Yes** |
| user | `--scope user` | `~/.claude.json` | No |

Add Playwright at project scope, from the project folder:

```powershell
claude mcp add --transport stdio --scope project playwright -- npx -y @playwright/mcp@latest
```

Resulting `.mcp.json` (add the optional flags by editing it):

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest", "--headless", "--output-dir", ".playwright-mcp"]
    }
  }
}
```

Add `.playwright-mcp/` to `.gitignore`.

Verify: `claude mcp list`, `claude mcp get playwright`, and `/mcp` inside a session. Project-scoped servers need a one-time approval. Reset with `claude mcp reset-project-choices`.

> **UNVERIFIED Windows workaround.** If the server reports "Failed to connect" and `npx` is the cause, try `-- cmd /c npx -y @playwright/mcp@latest`.

> Playwright MCP is **not a security boundary**. Treat anything it reads as untrusted.

### A.8 Subagents, skills and slash commands

| Feature | Location | Context | Invoked by |
|---|---|---|---|
| Subagent | `.claude/agents/<name>.md` | Own window; only its summary returns | Its `description`, or "use the X subagent" |
| Skill | `.claude/skills/<name>/SKILL.md` | Loaded into the conversation | Automatically, or `/<name>` |
| Command | `.claude/commands/<name>.md` | Older format | `/<name>` |

Create these three.

`.claude/agents/ui-verifier.md`:

```markdown
---
name: ui-verifier
description: Checks one built route against its acceptance criteria in docs/PRD.md using Playwright screenshots. Use after every UI change.
disallowedTools: Write, Edit
model: sonnet
---
You verify one route at a time.
1. Read that route's acceptance criteria from docs/PRD.md section 8.
2. Navigate with playwright-cli. Resize to 1280, 1440 and 1920 and screenshot each.
3. Take an accessibility snapshot. Check for unlabeled icon buttons, non-`th` table headers,
   and a virtualized grid exposing all rows to assistive technology.
4. Report PASS or FAIL per criterion with specific visual defects. Do not edit files.
```

`.claude/agents/invariant-auditor.md`:

```markdown
---
name: invariant-auditor
description: Verifies PRD section 4.3 invariants and hunts for hardcoded numbers anywhere in the codebase. Run before every commit.
disallowedTools: Write, Edit
model: sonnet
---
1. Run the invariant tests. Report any failure with the offending entity id.
2. Grep src/ and api/ for hardcoded percentages, currency symbols and thousands separators.
   Every number must flow through lib/format.ts or the API.
3. Grep every committed file for absolute local paths (C:\, D:\, /Users/, /home/).
4. Grep the dataset and source for real listed-company names.
Report findings as file:line. Do not fix anything.
```

`.claude/skills/ship-milestone/SKILL.md`:

```markdown
---
name: ship-milestone
description: Completes one PRD milestone: lint, test, verify the UI, audit invariants, commit.
disable-model-invocation: true
---
1. Run `npm run lint`, `npm test` and `pytest`. Fix failures before continuing.
2. Ensure both servers are running. Verify every acceptance criterion for this milestone
   with the ui-verifier subagent.
3. Run the invariant-auditor subagent. Any finding blocks the commit.
4. Show `git status` and a short diff summary.
5. Stage only this milestone's files. Commit as "feat(<area>): <milestone>".
6. Report what passed, what failed, and which PRD items remain open.
```

### A.9 The build loop

1. **Baseline.** Commit the PRD, `CLAUDE.md`, `.claude/` and `.mcp.json`. `git tag baseline`.
2. **Milestone 0.** `/plan` a scaffold with both servers running and one placeholder route. Approve with "manually approve edits". Confirm it runs. `/ship-milestone`.
3. **Each milestone, repeat:**
   - `/clear` for a fresh context. `CLAUDE.md` reloads automatically.
   - `/plan Implement PRD section 8.4 (Banking register) against its acceptance criteria.` Review, `Ctrl+G` to edit, approve.
   - Let Claude build.
   - "Use the ui-verifier subagent on /console." Fix any FAIL in the same session.
   - `/ship-milestone`.
   - Check `/context`. If large, `/compact keep the PRD section and file list`, or `/clear`.
4. **Checkpoints.** `Esc` twice or `/rewind` restores to an earlier prompt. Limits: tracks only edits made with Claude's file tools, not Bash changes such as `rm`, `mv` or `npm install`; keeps the 100 most recent. It is not version control. Git commits are the real safety net.
5. **Parallel work.** `claude --worktree <name>` gives an isolated checkout on its own branch. Use it only for independent milestones.

### A.10 Visual verification loop

Run `npm run dev` in a separate terminal and leave it. Then:

```bash
playwright-cli open http://localhost:5173/console
playwright-cli resize 1440 900
playwright-cli snapshot                    # accessibility tree, returns refs e1, e2…
playwright-cli screenshot --filename=console-1440.png --hires
playwright-cli resize 1280 800
playwright-cli screenshot --filename=console-1280.png --hires
playwright-cli close
```

Read the PNGs, critique against the acceptance criteria, fix, repeat. **Cap at three rounds.** Then lock it with `expect(page).toHaveScreenshot()` per panel and `--update-snapshots` on intentional changes.

`npx playwright init-skills --loop claude` installs three agent skills into `.claude/skills/`: `playwright-cli`, `playwright-trace` and `playwright-component-testing`.

> Prefer `playwright-cli` over the MCP server in Claude Code: the session persists across Bash calls and it costs no MCP tool-definition context. Use the MCP server when the client is Cursor or Windsurf.

### A.11 Troubleshooting

| Symptom | Fix |
|---|---|
| `claude` not recognized | §A.2. Open a new terminal; restart VS Code |
| `'irm' is not recognized` | You are in CMD. Use PowerShell |
| `The token '&&' is not a valid statement separator` | CMD syntax in PowerShell |
| Requires Git for Windows or PowerShell | Install Git for Windows |
| Git Bash not found | `{"env": {"CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"}}` |
| Settings error on startup | Remove comments and trailing commas. Run `/status` and `claude doctor` |
| MCP "Pending approval" | Trust the folder, approve the server interactively |

Useful: `/context` · `/compact [focus]` · `/clear` · `/rewind` · `/permissions` · `/mcp` · `/usage` · `/doctor` · `/model` · `/effort`

---

## Appendix B — Design tooling, with corrections

You named seven targets. Several resolve to something different from the name. Corrections first.

| You said | Actually | Verdict |
|---|---|---|
| SiteReel.ai | sitereel.ai | Name right. **Do not use.** It is a website prompt library for marketing sites. Pricing could not be verified. "Luxury landing page" prompts are actively wrong direction for an ops terminal |
| 21st.dev | 21st.dev | Right. "Magic MCP" is the **deprecated** name; it is now the unified **21st MCP**, and old Magic API keys were reset |
| tasteskill | `Leonxlnx/taste-skill` | Repo is `taste-skill`. `gpt-tasteskill` is one skill inside it |
| web-design guidelines | `vercel-labs/web-interface-guidelines` + the `web-design-guidelines` skill in `vercel-labs/agent-skills` | Two artifacts, both real |
| awsome-design-md | `VoltAgent/awesome-design-md` | Exact name exists |
| Image to code | `abi/screenshot-to-code`, **and** an `image-to-code` skill inside taste-skill | Ambiguous; both real |
| playwright-cli | `npx playwright cli`, new in Playwright 1.64 | **Real and first-class.** Not a misremembering |

### B.1 Ranked by usefulness to this project

**1. Vercel Web Interface Guidelines — highest value.** A ~130-rule checklist. Wire the skill as a pre-commit gate:

```bash
npx skills add https://github.com/vercel-labs/agent-skills --skill "web-design-guidelines"
```

The skill re-fetches `command.md` on every run, so it never goes stale. The `tabular-nums`, virtualization, `color-scheme: dark`, `Intl.NumberFormat` and URL-state rules in §11 come from it, and they are exactly the failure modes a treasury dashboard hits. Sibling worth adding: `react-best-practices`.

**2. playwright-cli — the agent's self-review loop.** §A.10. Nothing else on the list changes build quality as much.

**3. `VoltAgent/awesome-design-md` — visual reference.** 84 `DESIGN.md` files reverse-engineered from production sites. Directly relevant: **Kraken** (data-dense dark dashboards), **Sentry** (dark, data-dense), **Linear** (ultra-minimal), **Mercury** (banking), **Binance** (trading-floor urgency), **Vercel** (Geist), **IBM** (Carbon).

> Linear publishes **no public UI design system**, only brand guidelines covering logo and wordmark. The Linear "look" is available only through third-party extraction, which is what this repo is. Do not cite a Linear design system doc; it does not exist.

> These are third-party extractions of publicly visible CSS, offered as-is. Use them as direction. Do not copy a competitor's brand colours wholesale.

**4. 21st.dev — a parts bin, not the data layer.** Components install in shadcn registry format:

```bash
npx shadcn@latest add "https://21st.dev/r/<author>/<component>?api_key=$API_KEY_21ST"
```

MCP: `npx @21st-dev/cli@latest init --client claude`.

Pricing (billed yearly): Free = browse plus **2 component copies per day** · Builder $6/mo = unlimited copies, MCP and CLI retrieval, icons · Builder + AI $15/mo = 500–2,000 AI credits · Team $7.50/seat/mo.

Budget the $6 tier so the 2-per-day cap does not block a sprint. The registry skews marketing, so take the command palette, toolbars and sheets from it, and build the grid on shadcn/ui plus TanStack Table.

**5. taste-skill — install the right skill only.**

```bash
npx skills add https://github.com/Leonxlnx/taste-skill --skill "minimalist-ui"
```

> **Critical.** The repo's own FAQ states the default `design-taste-frontend` skill is **not** for dashboards or app screens, and directs you to the minimalist or soft variants. Install `minimalist-ui` and `full-output-enforcement`. **Do not install `design-taste-frontend`.**

**6. screenshot-to-code — limited use.** It reproduces one static screen, Tailwind-flat, with no state, no data layer and no virtualization. Useful only for extracting a spacing and colour skeleton from a reference screenshot, which you then throw away. Its model list changes constantly, so do not pin versions.

**7. SiteReel.ai — skip.** Marketing-site oriented. Wrong register for this product.

---

## Appendix C — What v1 got wrong

Carry these forward as regression tests, not just lessons.

| # | Defect in v1 | Prevention in v2 |
|---|---|---|
| 1 | India HQ named `Godrej Consumer Products Ltd (HQ)`, a real listed issuer, carrying invented financials | §12.2 naming rules; `invariant-auditor` greps for real company names |
| 2 | `README.md` and `generate_data.py` contained an absolute path with another person's username and the AI tool that generated it | §13 repo hygiene; `invariant-auditor` greps for absolute paths |
| 3 | Cash visibility shown as 93.8% in a tile and 95.1% in prose on the same screen | INV-3; grep test for hardcoded percentages |
| 4 | UK deployable surplus shown as £22.14M on one register and £18.5M on another | INV-1 and INV-2 enforced in the generator and the API |
| 5 | "UK operating buffer £10.1M" reconciled to nothing | INV-2 makes the buffer a derived value, not a literal |
| 6 | README referenced "PRD Section 4.8", "GLG-30", "UI-32" — a document nobody had | This PRD is committed at `docs/PRD.md` and is the only referent |
| 7 | 6,248-line single JS bundle, no types, no tests | TypeScript strict, Vitest, Playwright, one milestone per commit |
| 8 | "LOC-1 Assessment" was an invented term presented as standard | Replaced by the Route A–D model with real regulatory citations |
| 9 | Repo was public before judging | Private until results are announced |
| 10 | Single "Initial commit" dump | One commit per milestone, each with passing acceptance criteria |

---

## Appendix D — Open items to resolve before the finale

| Item | Risk | How to close |
|---|---|---|
| Rule 10TD renumbering under Income-tax Rules 2026 | Citing a superseded rule | Find the gazette notification. Fallback: cite the 1962 Rules with the sub-rule (3B) applicability note |
| Whether a 9 June 2025 IFSCA GRCTC framework supersedes the 4 April 2025 one | Wrong clause numbers on the flagship claim | Navigate `ifsca.gov.in/Legal` |
| Numeric all-in-cost ceiling under the post-February-2026 ECB regime | Cost-of-funds model unsourced | Read the current trade-credit ceiling in the amended Regulations, not the old Master Direction |
| Whether a 2025/26 Interest Rate on Deposits Direction superseded the 2016 one | Wrong clause for the current-account prohibition | RBI Master Directions index |
| Income-tax Act 2025 section replacing s.94B | Citing a repealed section | CBDT section-mapping table |
| SR2026 structured-address extension | Quoting 14 Nov 2026 as immovable when it may have moved | SWIFT ISO 20022 programme page |
