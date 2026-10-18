/**
 * Loading, empty, error, stale and partial (PRD 8.11).
 *
 * These are the normal case in treasury, not the exception. Each one is
 * designed rather than defaulted: a centred spinner over a table, a bare
 * "No data", or an aggregate with no coverage figure would each be a defect.
 */

import type { ReactNode } from 'react';
import { AlertTriangle, Ban, Clock, Inbox, RefreshCw, WifiOff } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { Badge, Button, cn } from './primitives';
import type { Coverage } from '@/lib/types';

/** Skeleton rows match the final row height exactly, so nothing shifts. */
export function SkeletonRows({
  rows = 8,
  cols = 5,
  dense = false,
}: {
  rows?: number;
  cols?: number;
  dense?: boolean;
}) {
  const height = dense ? 'h-[24px]' : 'h-[32px]';
  return (
    <div aria-busy="true" aria-live="polite" className="w-full">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }, (_, row) => (
        <div
          key={row}
          className={cn('flex items-center gap-3 border-b border-[var(--border-subtle)] px-2.5', height)}
        >
          {Array.from({ length: cols }, (_, col) => (
            <div
              key={col}
              className="skeleton h-[10px]"
              style={{ width: col === 0 ? '18%' : `${10 + ((col * 7) % 14)}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div aria-busy="true" className={cn('skeleton', className)}>
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/**
 * Nothing has been produced yet. States what is missing, who owns it, and the
 * action. Never "No data" on its own.
 */
export function EmptyState({
  what,
  owner,
  action,
  onAction,
}: {
  what: string;
  owner?: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-2 p-5">
      <Inbox size={16} className="text-[var(--text-tertiary)]" aria-hidden />
      <p className="text-[13px] text-[var(--text-primary)]">{what}</p>
      {owner ? <p className="text-[12px] text-[var(--text-tertiary)]">Owner: {owner}</p> : null}
      {action && onAction ? (
        <Button variant="secondary" onClick={onAction}>
          {action}
        </Button>
      ) : null}
    </div>
  );
}

/** Filtered to nothing. Distinct from "not produced yet", and says which filters. */
export function FilteredEmpty({
  filters,
  onClear,
}: {
  filters: string[];
  onClear: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-2 p-5">
      <p className="text-[13px] text-[var(--text-primary)]">
        No rows match the current filters.
      </p>
      <p className="text-[12px] text-[var(--text-tertiary)]">
        Applied: {filters.length ? filters.join(' · ') : 'none'}
      </p>
      <Button variant="secondary" onClick={onClear}>
        Clear filters
      </Button>
    </div>
  );
}

/**
 * Inline, in place, with a retry. Never a toast that disappears: the register
 * must stay usable and the reader must be able to read the reason twice.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const problem = error instanceof ApiError ? error.problem : null;
  const forbidden = error instanceof ApiError && error.isForbidden;

  return (
    <div
      role="alert"
      className="m-3 flex flex-col items-start gap-2 rounded-[4px] p-4"
      style={{
        background: forbidden ? 'var(--warn-3)' : 'var(--err-3)',
        boxShadow: `inset 0 0 0 1px ${forbidden ? 'var(--warn-9)' : 'var(--err-9)'}`,
      }}
    >
      <div className="flex items-center gap-2">
        {forbidden ? (
          <Ban size={15} style={{ color: 'var(--warn-11)' }} aria-hidden />
        ) : (
          <AlertTriangle size={15} style={{ color: 'var(--err-11)' }} aria-hidden />
        )}
        <p className="text-[13px] font-semibold text-[var(--text-primary)]">
          {problem?.title ?? 'The request failed.'}
        </p>
      </div>
      <p className="max-w-[72ch] text-[12px] text-[var(--text-secondary)]">
        {problem?.detail ?? 'An unexpected error occurred. Nothing was changed.'}
      </p>
      {onRetry && !forbidden ? (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={13} aria-hidden />
          Retry
        </Button>
      ) : null}
    </div>
  );
}

/**
 * A stale figure still renders. Hiding it would make the group look more
 * current than it is, which is the opposite of the product's job.
 */
export function StaleBadge({ status, age }: { status: string; age?: string }) {
  if (status === 'live') return null;
  if (status === 'offline') {
    return (
      <Badge tone="err" glyph={<WifiOff size={10} aria-hidden />} title={`Feed offline. ${age ?? ''}`}>
        offline{age ? ` · ${age}` : ''}
      </Badge>
    );
  }
  return (
    <Badge tone="warn" glyph={<Clock size={10} aria-hidden />} title={`Feed stale. ${age ?? ''}`}>
      stale{age ? ` · ${age}` : ''}
    </Badge>
  );
}

/**
 * Every aggregate carries its coverage. An aggregate without one is a lie by
 * omission, and v1 showed a total beside a stale chip and called it reconciled.
 */
export function CoverageNote({ coverage, className }: { coverage: Coverage; className?: string }) {
  const complete = coverage.accounts_current === coverage.accounts_total;
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-[11px]', className)}
      style={{ color: complete ? 'var(--text-tertiary)' : 'var(--warn-11)' }}
      title={
        complete
          ? 'Every contributing account feed is current.'
          : 'Some contributing feeds are stale or offline. The figure is shown with its coverage rather than hidden.'
      }
    >
      {complete ? null : <AlertTriangle size={10} aria-hidden />}
      {coverage.statement}
    </span>
  );
}

export function QueryBoundary<T>({
  query,
  skeleton,
  children,
  empty,
}: {
  query: { data: T | undefined; isPending: boolean; error: unknown; refetch: () => void };
  skeleton?: ReactNode;
  empty?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <>{skeleton ?? <SkeletonRows />}</>;
  if (query.error) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data === undefined) return <>{empty ?? <EmptyState what="Nothing was returned." />}</>;
  if (Array.isArray(query.data) && query.data.length === 0 && empty) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
