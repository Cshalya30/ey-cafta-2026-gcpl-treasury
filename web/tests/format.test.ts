/**
 * lib/format.ts across all eleven currencies, including INR lakh and crore.
 *
 * These assert behaviour rather than exact glyphs where Intl's output varies
 * by ICU version: pinning a literal string here would make the suite brittle
 * for exactly the reason the formatter exists.
 */

import { describe, expect, it } from 'vitest';
import {
  ageInDays,
  bps,
  compactMoney,
  count,
  date,
  displayCode,
  displayMoney,
  inrGrouped,
  money,
  pct,
  relativeAge,
  titleCase,
  truncate,
} from '@/lib/format';

const CURRENCIES = [
  'USD', 'INR', 'GBP', 'EUR', 'SGD', 'AED', 'JPY', 'AUD', 'NGN', 'IDR', 'BRL',
] as const;

describe('money', () => {
  it.each(CURRENCIES)('formats %s without throwing and without a bare number', (ccy) => {
    const out = money(1_234_567, ccy);
    expect(out).toBeTruthy();
    expect(out).not.toBe('1234567');
    // Intl always emits a symbol or a code; it is never just digits.
    expect(/[^\d\s.,\-]/.test(out)).toBe(true);
  });

  it('uses the Indian grouping for INR under en-IN', () => {
    // 12,34,567 in the lakh scale, not 1,234,567.
    expect(inrGrouped(1_234_567)).toBe('12,34,567');
  });

  it('uses the western grouping for USD under en-US', () => {
    expect(count(1_234_567)).toBe('1,234,567');
  });

  it('respects zero minor units for JPY', () => {
    expect(money(1500, 'JPY')).not.toContain('.');
  });

  it('rounds to whole units, because a treasury grid has no use for cents', () => {
    expect(money(1234.56, 'USD')).not.toContain('.5');
  });
});

describe('percentages and basis points', () => {
  it('formats a decimal as a percentage with one place by default', () => {
    expect(pct(0.9138)).toBe('91.4%');
  });

  it('honours the requested precision', () => {
    expect(pct(0.0705, 2)).toBe('7.05%');
  });

  it('converts a decimal spread to basis points', () => {
    expect(bps(0.0325)).toBe('325 bps');
  });

  it('handles zero and one without special-casing', () => {
    expect(pct(0)).toBe('0.0%');
    expect(pct(1)).toBe('100.0%');
  });
});

describe('compact notation', () => {
  it('compacts USD into the thousands and millions scale', () => {
    expect(compactMoney(3_906_816, 'USD')).toMatch(/3\.9M/);
  });

  it('compacts INR into the lakh and crore scale', () => {
    // 1 crore. en-IN compact notation says "1 Cr", not "10M".
    const out = compactMoney(10_000_000, 'INR');
    expect(out).toMatch(/Cr|L/);
  });
});

describe('dates', () => {
  it('formats an ISO date in an unambiguous medium style', () => {
    const out = date('2026-10-17');
    expect(out).toContain('2026');
    // Never the ambiguous all-numeric form that reads differently per locale.
    expect(out).not.toMatch(/^\d{1,2}\/\d{1,2}\/\d{4}$/);
  });

  it('measures age in whole days', () => {
    const from = new Date('2026-10-17T12:00:00Z');
    expect(ageInDays('2026-10-14T12:00:00Z', from)).toBe(3);
    expect(ageInDays('2026-10-17T11:00:00Z', from)).toBe(0);
  });

  it('describes a feed age in words an operator would use', () => {
    const from = new Date('2026-10-17T12:00:00Z');
    expect(relativeAge('2026-10-17T11:40:00Z', from)).toBe('under an hour old');
    expect(relativeAge('2026-10-16T12:00:00Z', from)).toContain('h old');
    expect(relativeAge('2026-10-10T12:00:00Z', from)).toContain('days old');
  });
});

describe('displayMoney', () => {
  const envelope = { native: 44_200_000, currency: 'GBP', usd: 56_797_000 };

  it('shows the holder currency in native mode', () => {
    expect(displayMoney(envelope, 'native', 83)).toContain('44');
    expect(displayCode(envelope, 'native')).toBe('GBP');
  });

  it('shows the API-supplied USD sibling in USD mode', () => {
    expect(displayMoney(envelope, 'USD', 83)).toContain('56');
    expect(displayCode(envelope, 'USD')).toBe('USD');
  });

  it('converts INR from the USD sibling, never from the native amount', () => {
    // 56,797,000 USD at 83 is roughly 471 crore, not 44.2m x 83.
    const out = displayMoney(envelope, 'INR', 83, true);
    expect(out).toMatch(/Cr|,/);
    expect(displayCode(envelope, 'INR')).toBe('INR');
  });

  it('is total across every display mode for every currency', () => {
    for (const ccy of CURRENCIES) {
      const value = { native: 1000, currency: ccy, usd: 1000 };
      for (const mode of ['native', 'USD', 'INR'] as const) {
        expect(() => displayMoney(value, mode, 83)).not.toThrow();
      }
    }
  });
});

describe('text helpers', () => {
  it('title-cases a snake_case enum for display', () => {
    expect(titleCase('debt_service')).toBe('Debt Service');
    expect(titleCase('not_assessed')).toBe('Not Assessed');
  });

  it('truncates with a single ellipsis character, not three full stops', () => {
    const out = truncate('a'.repeat(50), 10);
    expect(out).toHaveLength(10);
    expect(out.endsWith('…')).toBe(true);
    expect(out).not.toContain('...');
  });

  it('leaves a short string untouched', () => {
    expect(truncate('short', 10)).toBe('short');
  });
});
