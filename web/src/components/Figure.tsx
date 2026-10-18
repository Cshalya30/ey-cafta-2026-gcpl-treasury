/**
 * Every money figure on screen renders through this component, which renders
 * through lib/format.ts. There is no other path from a number to the DOM.
 */

import { displayCode, displayMoney } from '@/lib/format';
import type { Money } from '@/lib/types';
import { getUsdToInr, useUi } from '@/lib/store';
import { cn } from './primitives';

export function Figure({
  value,
  compact = false,
  className,
  showCode = false,
}: {
  value: Money;
  compact?: boolean;
  className?: string;
  showCode?: boolean;
}) {
  const display = useUi((state) => state.display);
  const text = displayMoney(value, display, getUsdToInr(), compact);
  return (
    <span className={cn('tnum', className)}>
      {/* Currency codes are brand-like tokens and must not be machine-translated. */}
      {showCode ? (
        <span translate="no" className="mr-1 text-[var(--text-tertiary)]">
          {displayCode(value, display)}
        </span>
      ) : null}
      {text}
    </span>
  );
}

/** A bare USD amount from the API, where no native sibling exists. */
export function UsdFigure({
  usd,
  compact = false,
  className,
}: {
  usd: number;
  compact?: boolean;
  className?: string;
}) {
  return (
    <Figure value={{ native: usd, currency: 'USD', usd }} compact={compact} className={className} />
  );
}
