/** Small shared primitives. Status always pairs hue with a glyph or a number. */

import type { ReactNode } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...parts: (string | false | null | undefined)[]): string =>
  twMerge(clsx(parts));

export type Tone = 'ok' | 'warn' | 'err' | 'info' | 'accent' | 'neutral';

const TONE_STYLE: Record<Tone, { dot: string; text: string; tint: string; border: string }> = {
  ok: { dot: 'var(--ok-9)', text: 'var(--ok-11)', tint: 'var(--ok-3)', border: 'var(--ok-9)' },
  warn: {
    dot: 'var(--warn-9)',
    text: 'var(--warn-11)',
    tint: 'var(--warn-3)',
    border: 'var(--warn-9)',
  },
  err: { dot: 'var(--err-9)', text: 'var(--err-11)', tint: 'var(--err-3)', border: 'var(--err-9)' },
  info: {
    dot: 'var(--info-9)',
    text: 'var(--info-11)',
    tint: 'var(--info-3)',
    border: 'var(--info-9)',
  },
  accent: {
    dot: 'var(--accent-9)',
    text: 'var(--accent-11)',
    tint: 'var(--surface-3)',
    border: 'var(--accent-9)',
  },
  neutral: {
    dot: 'var(--stale-9)',
    text: 'var(--text-tertiary)',
    tint: 'var(--stale-3)',
    border: 'var(--border-strong)',
  },
};

/**
 * A status dot. Always rendered beside its own label, never alone: colour
 * carries no quantity on its own and a dot with no text is unreadable to a
 * viewer who does not perceive the hue.
 */
export function Dot({ tone, title }: { tone: Tone; title: string }) {
  return (
    <span
      role="img"
      aria-label={title}
      title={title}
      className="inline-block size-[7px] shrink-0 rounded-full"
      style={{ background: TONE_STYLE[tone].dot }}
    />
  );
}

export function Badge({
  tone = 'neutral',
  children,
  glyph,
  className,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  glyph?: ReactNode;
  className?: string;
  title?: string;
}) {
  const style = TONE_STYLE[tone];
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-[2px] px-1.5 py-px text-[11px] font-medium leading-[16px]',
        className,
      )}
      style={{ background: style.tint, color: style.text, boxShadow: `inset 0 0 0 1px ${style.border}` }}
    >
      {glyph}
      {children}
    </span>
  );
}

/** Route A to D. The letter always travels with the colour. */
export function RouteBadge({ route, className }: { route: string; className?: string }) {
  const colour =
    route === 'A'
      ? 'var(--route-a)'
      : route === 'B'
        ? 'var(--route-b)'
        : route === 'C'
          ? 'var(--route-c)'
          : 'var(--route-d)';
  const label: Record<string, string> = {
    A: 'Route A, India domestic',
    B: 'Route B, offshore regional',
    C: 'Route C, India cross-border',
    D: 'Route D, restricted',
  };
  return (
    <span
      title={label[route] ?? `Route ${route}`}
      className={cn(
        'ident inline-flex items-center justify-center rounded-[2px] px-1.5 text-[11px] font-semibold leading-[16px]',
        className,
      )}
      style={{ color: colour, boxShadow: `inset 0 0 0 1px ${colour}` }}
    >
      {route}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = 'secondary',
  disabled,
  type = 'button',
  title,
  className,
  'aria-pressed': ariaPressed,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  disabled?: boolean;
  type?: 'button' | 'submit';
  title?: string;
  className?: string;
  'aria-pressed'?: boolean;
}) {
  const base =
    'press inline-flex h-7 items-center gap-1.5 rounded-[3px] px-2.5 text-[12px] font-medium disabled:cursor-not-allowed disabled:opacity-45';
  const variants: Record<string, string> = {
    // Hover and active are MORE prominent than rest, not merely different.
    primary:
      'bg-[var(--accent-9)] text-white hover:bg-[var(--accent-10)]',
    secondary:
      'bg-[var(--surface-3)] text-[var(--text-primary)] hover:bg-[var(--surface-4)] shadow-[inset_0_0_0_1px_var(--border-interactive)]',
    ghost: 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]',
    danger: 'bg-[var(--err-9)] text-white hover:brightness-110',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-pressed={ariaPressed}
      className={cn(base, variants[variant], className)}
    >
      {children}
    </button>
  );
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
}: {
  title?: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        'flex min-h-0 min-w-0 flex-col rounded-[4px] bg-[var(--surface-2)]',
        'shadow-[inset_0_0_0_1px_var(--border-subtle)]',
        className,
      )}
    >
      {title ? (
        <header className="flex h-8 shrink-0 items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-3">
          <div className="flex min-w-0 items-baseline gap-2">
            <h2 className="truncate text-[12px] font-semibold tracking-[0.02em] uppercase text-[var(--text-secondary)]">
              {title}
            </h2>
            {subtitle ? (
              <span className="truncate text-[11px] text-[var(--text-tertiary)]">{subtitle}</span>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-1">{actions}</div> : null}
        </header>
      ) : null}
      {/* Focusable: a scrollable region a keyboard user cannot reach is a
          WCAG 2.1.1 failure, and this body scrolls on every dense panel. */}
      <div
        tabIndex={0}
        role={title ? 'group' : undefined}
        aria-label={title}
        className="min-h-0 min-w-0 flex-1 overflow-auto"
      >
        {children}
      </div>
    </section>
  );
}

export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-[11px] font-medium text-[var(--text-secondary)]">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-[11px] text-[var(--err-11)]">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-[11px] text-[var(--text-tertiary)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** A labelled statistic. The label is always present; the number never floats alone. */
export function Stat({
  label,
  value,
  sub,
  tone = 'neutral',
  mono = true,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: Tone;
  mono?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="truncate text-[11px] text-[var(--text-tertiary)]">{label}</span>
      <span
        className={cn('truncate text-[15px] font-semibold', mono && 'tnum')}
        style={{ color: tone === 'neutral' ? 'var(--text-primary)' : TONE_STYLE[tone].text }}
      >
        {value}
      </span>
      {sub ? <span className="truncate text-[11px] text-[var(--text-tertiary)]">{sub}</span> : null}
    </div>
  );
}
