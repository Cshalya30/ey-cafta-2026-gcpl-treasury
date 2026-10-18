/**
 * A figure that acknowledges its own change.
 *
 * When a computed number moves under the reader — a slider is dragged, a rate
 * is edited, a persona switch rescopes the aggregate — the value settles into
 * place rather than swapping silently. That is the one animation in this
 * product with a job: it marks causation, which is the Cash Leak's whole point.
 *
 * It does nothing on first paint (a page load is not a change) and nothing
 * under prefers-reduced-motion, where the token collapses to 1ms.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { cn } from './primitives';

export function LiveValue({
  value,
  children,
  className,
}: {
  /** The dependency that marks a real change. Usually the raw number. */
  value: number | string;
  children: ReactNode;
  className?: string;
}) {
  const [pulse, setPulse] = useState(false);
  const previous = useRef<number | string | null>(null);

  useEffect(() => {
    // First paint is not a change, so it is not announced.
    if (previous.current === null) {
      previous.current = value;
      return;
    }
    if (previous.current === value) return;

    previous.current = value;
    setPulse(true);
    const timer = window.setTimeout(() => setPulse(false), 240);
    return () => window.clearTimeout(timer);
  }, [value]);

  return (
    <span
      // Polite: a treasury figure updating is worth announcing, but never
      // worth interrupting whatever the screen reader is already saying.
      aria-live="polite"
      className={cn(pulse && 'animate-value', className)}
    >
      {children}
    </span>
  );
}
