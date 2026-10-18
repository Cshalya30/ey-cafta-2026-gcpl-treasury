# GCPL Treasury Command

## Source of truth
- Product spec: `docs/PRD.md`. Before coding a feature, read the section it names.
- Do not edit `docs/PRD.md`. If it is ambiguous, ask before building.
- Design contract: `docs/DESIGN.md`. Non-obvious choices are recorded in `docs/decisions/`.

## What this is, and is not
- It is a Phase 0 control layer and a TMS requirements specification.
- **It is not a Treasury Management System** and must never be described as one.
- It never moves money. It proposes, validates and records.
- All data is synthetic. The watermark ribbon is load-bearing; a test asserts it.

## Commands
- Seed: `python scripts/generate_data.py --seed 42`
- API: `.venv/Scripts/python -m uvicorn api.main:app --reload --port 8000`
- Web: `cd web && npm run dev` (http://localhost:5173)
- Test: `python -m pytest` and `cd web && npm test`
- E2E: `cd web && npm run e2e`
- Lint types: `cd web && npm run typecheck`

## Working rules
- One PRD milestone per session. Commit after each. Never bundle two milestones.
- TypeScript strict. No `any` in `web/src/`.
- All numbers format through `web/src/lib/format.ts`. Never hardcode a currency
  symbol, a percentage or a thousands separator.
- ABAC is enforced server-side only. Never filter by persona in the browser.
  An out-of-scope entity returns 403, not a filtered 200.
- Every endpoint declares `current_scope`. A test enumerates the route table.
- `audit_event` is append-only. There is no update or delete path, anywhere.
- After any UI change, verify the route with the `ui-verifier` subagent against
  that milestone's acceptance criteria.

## Invariants that must never regress
- **INV-1** `total_cash = available_local + restricted`; `deployable_surplus` is a
  subset of `available_local`, never additive.
- **INV-2** `operating_buffer = available_local - deployable_surplus >= 0`.
- **INV-3** Cash visibility is computed from `feed_status` alone. No hardcoded
  percentage may appear anywhere in the codebase.

## Motion
- Animate `transform` and `opacity` only. Never `transition: all`.
- Tokens live in `web/src/styles/motion.css`. Use them; do not invent durations.
- Leaving is ~75% of entering.
- Every duration collapses to 1ms under `prefers-reduced-motion`.
- The leak edge is the only looping animation and it stops under reduced motion.

## CSS cascade
Tailwind v4 puts utilities in a cascade layer. **Unlayered CSS beats layered CSS
regardless of specificity.** Base element styles therefore live in `@layer base`
and custom classes in `@layer components`, and vendor stylesheets are imported
with `layer(base)`. Writing an unlayered `a { color: … }` silently overrides
`text-white` and has already caused one contrast failure.
