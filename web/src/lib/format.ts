/**
 * The ONLY place numbers become strings.
 *
 * Never hardcode a currency symbol or a thousands separator. v1 did, in
 * data.js, and shipped four contradictory figures as a result. Intl knows the
 * symbol, the grouping and the minor units for all eleven currencies here,
 * including the lakh and crore grouping that en-IN applies to INR.
 */

export type Money = {
  readonly native: number;
  readonly currency: string;
  readonly usd: number;
};

export type DisplayCurrency = 'native' | 'USD' | 'INR';

/** Intl formatters are expensive to construct; one per key is plenty. */
const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();

function memo<T extends Intl.NumberFormat | Intl.DateTimeFormat>(key: string, build: () => T): T {
  let found = cache.get(key);
  if (!found) {
    found = build();
    cache.set(key, found);
  }
  return found as T;
}

const formatter = (key: string, build: () => Intl.NumberFormat): Intl.NumberFormat =>
  memo(key, build);

const dateFormatter = (key: string, build: () => Intl.DateTimeFormat): Intl.DateTimeFormat =>
  memo(key, build);

/**
 * The grouping locale follows the currency, not the reader.
 *
 * en-IN groups in lakh and crore, which is right for INR and wrong for
 * everything else: defaulting every currency to en-IN renders 56,797,000 USD
 * as "$5,67,97,000", which no treasurer outside India would read correctly.
 */
const localeFor = (ccy: string): string => (ccy === 'INR' ? 'en-IN' : 'en-US');

export const money = (value: number, ccy: string, locale = localeFor(ccy)): string =>
  formatter(`m:${ccy}:${locale}`, () =>
    new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: ccy,
      maximumFractionDigits: 0,
    }),
  ).format(value);

/** Lakh and crore grouping. en-IN does this natively; do not hand-roll it. */
export const inrGrouped = (value: number): string =>
  formatter('inr-grouped', () =>
    new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }),
  ).format(value);

export const pct = (value: number, digits = 1): string =>
  formatter(`p:${digits}`, () =>
    new Intl.NumberFormat('en-US', {
      style: 'percent',
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }),
  ).format(value);

export const bps = (value: number): string =>
  `${formatter('bps', () => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })).format(
    value * 10_000,
  )} bps`;

export const count = (value: number): string =>
  formatter('count', () => new Intl.NumberFormat('en-US')).format(value);

export const date = (iso: string): string =>
  dateFormatter('date', () =>
    new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium' }),
  ).format(new Date(iso));

export const dateTime = (iso: string): string =>
  dateFormatter('datetime', () =>
    new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }),
  ).format(new Date(iso));

export const timeOnly = (iso: string): string =>
  dateFormatter('time', () =>
    new Intl.DateTimeFormat('en-GB', { timeStyle: 'medium' }),
  ).format(new Date(iso));

/**
 * Compact display for KPI posters and node badges.
 *
 * Intl's own compact notation is used rather than a hand-rolled k/M/B ladder,
 * so INR renders in the lakh and crore scale a reader in Mumbai expects and
 * USD renders in thousands and millions.
 */
export const compactMoney = (value: number, ccy: string): string => {
  const locale = localeFor(ccy);
  return formatter(`c:${ccy}:${locale}`, () =>
    new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: ccy,
      notation: 'compact',
      maximumFractionDigits: 1,
    }),
  ).format(value);
};

/** How many days ago, as an age badge reads it. */
export const ageInDays = (iso: string, from = new Date()): number => {
  const then = new Date(iso).getTime();
  return Math.max(0, Math.floor((from.getTime() - then) / 86_400_000));
};

export const relativeAge = (iso: string, from = new Date()): string => {
  const hours = Math.max(0, Math.round((from.getTime() - new Date(iso).getTime()) / 3_600_000));
  if (hours < 1) return 'under an hour old';
  if (hours < 48) return `${count(hours)} h old`;
  return `${count(Math.round(hours / 24))} days old`;
};

/**
 * Render an API money envelope in the currently selected display currency.
 *
 * `native` shows the holder's own currency. USD and INR convert through the
 * envelope's own usd sibling, so the browser never performs an FX calculation
 * of its own: the rate used is the one the API applied.
 */
export function displayMoney(
  value: Money,
  display: DisplayCurrency,
  usdToInr: number,
  compact = false,
): string {
  if (display === 'native') {
    return compact ? compactMoney(value.native, value.currency) : money(value.native, value.currency);
  }
  if (display === 'USD') {
    return compact ? compactMoney(value.usd, 'USD') : money(value.usd, 'USD');
  }
  const inr = value.usd * usdToInr;
  return compact ? compactMoney(inr, 'INR') : money(inr, 'INR');
}

/** The code shown beside a figure, so the unit is never ambiguous. */
export const displayCode = (value: Money, display: DisplayCurrency): string =>
  display === 'native' ? value.currency : display;

export const titleCase = (value: string): string =>
  value
    .replace(/_/g, ' ')
    .replace(/\b[a-z]/g, (character) => character.toUpperCase());

/** An ellipsis is a character, not three full stops. */
export const truncate = (value: string, max: number): string =>
  value.length <= max ? value : `${value.slice(0, Math.max(0, max - 1))}…`;
