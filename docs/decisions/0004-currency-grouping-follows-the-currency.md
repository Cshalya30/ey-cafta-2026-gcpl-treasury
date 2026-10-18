# 4. Number grouping follows the currency, not the reader

**Status** Accepted · **Date** 18 October 2026

## Context

PRD section 6.1 specifies `money()` with a default locale of `en-IN`:

```ts
export const money = (v: number, ccy: string, locale = 'en-IN') => …
```

`en-IN` groups in lakh and crore. Applied to every currency, 56,797,000 USD
renders as `$5,67,97,000`, which no treasurer outside India reads correctly.
A unit test across all eleven currencies caught it.

## Decision

Derive the grouping locale from the currency: `en-IN` for INR, `en-US` for
everything else. The parameter remains overridable.

INR therefore still renders in the lakh and crore scale a reader in Mumbai
expects — including `compactMoney`, which produces "1 Cr" rather than "10M" —
and every other currency groups in thousands.

## Consequences

- A deliberate deviation from the PRD snippet, recorded here.
- `lib/format.ts` is the only place a number becomes a string, so this was a
  one-line change with no call sites to audit. That is the payoff of the rule.
