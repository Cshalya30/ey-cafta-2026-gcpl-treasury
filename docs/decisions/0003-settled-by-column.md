# 3. `proposal.settled_by` is added to the PRD schema

**Status** Accepted · **Date** 18 October 2026

## Context

PRD section 4.2 defines `proposal` with `created_by`, `approved_by` and
`approved_at`, but no settlement columns. PRD section 5.2 nevertheless requires
`POST /proposals/{id}/settle` to reject the call "if settler was creator or
approver (LR4)".

LR4 cannot be evaluated against a value the schema does not store.

## Decision

Add `settled_by` and `settled_at` to the `proposal` table.

LR4's predicate then stays an ordinary data rule — `all_distinct` over
`created_by`, `approved_by` and `settled_by` — and remains a row in `sod_rule`
rather than becoming a special case inside the linter.

## Consequences

- The schema is a superset of PRD 4.2 by two columns. Nothing else changes.
- The settlement blotter shows the three independent holders side by side,
  which is the demonstration LR4 exists for.
