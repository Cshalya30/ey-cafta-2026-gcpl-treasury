# 1. The Cash Leak is allocated greedily, not summed over all pairs

**Status** Accepted · **Date** 18 October 2026

## Context

PRD section 5.3 states the method as: "For each (surplus entity, borrowing
entity) pair sharing a poolable route, overlap = MIN(deployable_surplus_usd,
drawn_facility_usd); leak = overlap x (all_in_rate - deposit_rate)."

Read literally over all pairs, that double-counts. With three surplus entities
and four borrowers, the same GBP surplus is matched against four separate
drawings, and the same US drawing against three separate surpluses. The headline
number would be several times the real figure.

The headline number is the product's reason to exist. A judge who checks it by
hand and finds it inflated has grounds to dismiss everything else on the screen.

## Decision

Keep the per-pair formula exactly as specified, and add a capacity constraint:

1. Rank surplus entities by deposit rate ascending (cheapest money first).
2. Rank borrowers by all-in rate descending (most expensive debt first).
3. Walk the borrowers, allocating available surplus greedily.
4. Consume capacity as it is allocated, so no surplus and no drawing is counted
   twice.

Route D entities are excluded before the walk and reported separately as trapped.

The ordering is not arbitrary: cheapest deposit against most expensive debt is
both the arrangement that maximises the measured leak and the one a treasurer
would actually unwind first. The method string returned by `GET /cash-leak`
states the allocation rule in full, so the figure is auditable from the response
alone.

## Consequences

- The total reconciles: summing `annualised_leak_usd` across `pairs` equals
  `total_annualised_usd`, and a test asserts it.
- Each pair's `overlap_usd` is the *allocated* overlap, which may be less than
  `MIN(surplus, drawn)` when capacity has already been consumed. The `detail`
  string shows the arithmetic actually used.
- This is a deliberate deviation from a literal reading of PRD 5.3. It is
  recorded here rather than silently applied.
