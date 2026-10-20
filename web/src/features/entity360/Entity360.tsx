/**
 * Entity 360 — a non-modal slide-over with thirteen tabs.
 *
 * Non-modal by design (PRD 11.5): a modal would hide the adjacent records a
 * treasury user is comparing against, which is the whole task.
 */

import { useEffect, useMemo, useState } from 'react';
import { useQueryState } from 'nuqs';
import { X } from 'lucide-react';
import {
  useAccounts,
  useAudit,
  useEntity,
  useExposures,
  useFacilities,
  useForecasts,
  useOnboarding,
  usePools,
  useRoutes,
  useNotionalPooling,
} from '@/lib/hooks';
import { Badge, Button, Dot, Panel, RouteBadge, Stat, cn } from '@/components/primitives';
import { CoverageNote, EmptyState, ErrorState, SkeletonRows, StaleBadge } from '@/components/states';
import { Figure, UsdFigure } from '@/components/Figure';
import { date, dateTime, pct, titleCase } from '@/lib/format';
import type { Entity } from '@/lib/types';

const TABS = [
  'Summary',
  'Cash and accounts',
  'Forecast',
  'Liquidity and pooling',
  'Funding and facilities',
  'Investments',
  'Exposures and hedging',
  'Payments and settlement',
  'Controls and exceptions',
  'Route assessment',
  'Activity stream',
  'Data health',
  'Service and SLA',
] as const;

export function Entity360({ entityId, onClose }: { entityId: string | null; onClose: () => void }) {
  const [tab, setTab] = useQueryState('tab', { defaultValue: TABS[0] });
  const entity = useEntity(entityId);

  useEffect(() => {
    if (!entityId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [entityId, onClose]);

  if (!entityId) return null;

  return (
    <aside
      aria-label="Entity 360"
      className="animate-slide-right flex w-[min(620px,46vw)] shrink-0 flex-col border-l border-[var(--border-strong)] bg-[var(--surface-2)]"
    >
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-[var(--border-subtle)] px-3 py-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-[14px] font-semibold" translate="no">
              {entity.data?.short_name ?? entityId}
            </h2>
            {entity.data ? <RouteBadge route={entity.data.route} /> : null}
            {entity.data?.is_hq ? <Badge tone="accent">HQ</Badge> : null}
          </div>
          <p className="truncate text-[11px] text-[var(--text-tertiary)]" translate="no">
            {entity.data?.legal_name ?? ''}
          </p>
        </div>
        <Button variant="ghost" onClick={onClose} title="Close (Escape)">
          <X size={14} aria-hidden />
        </Button>
      </header>

      <nav
        role="tablist"
        aria-label="Entity sections"
        className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-[var(--border-subtle)] px-2 py-1"
      >
        {TABS.map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            onClick={() => void setTab(name)}
            className={cn(
              'h-6 shrink-0 rounded-[3px] px-2 text-[11px] whitespace-nowrap transition-colors duration-100',
              tab === name
                ? 'bg-[var(--surface-4)] text-[var(--text-primary)]'
                : 'text-[var(--text-tertiary)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]',
            )}
          >
            {name}
          </button>
        ))}
      </nav>

      <div
        role="tabpanel"
        tabIndex={0}
        aria-label={tab}
        className="min-h-0 flex-1 overflow-auto p-3"
      >
        {entity.isPending ? (
          <SkeletonRows rows={10} cols={4} />
        ) : entity.error ? (
          <ErrorState error={entity.error} onRetry={() => entity.refetch()} />
        ) : entity.data ? (
          <TabBody tab={tab} entity={entity.data} />
        ) : null}
      </div>
    </aside>
  );
}

function TabBody({ tab, entity }: { tab: string; entity: Entity }) {
  switch (tab) {
    case 'Cash and accounts':
      return <CashTab entity={entity} />;
    case 'Forecast':
      return <ForecastTab entity={entity} />;
    case 'Liquidity and pooling':
      return <PoolingTab entity={entity} />;
    case 'Funding and facilities':
      return <FundingTab entity={entity} />;
    case 'Investments':
      return <InvestmentsTab entity={entity} />;
    case 'Exposures and hedging':
      return <ExposuresTab entity={entity} />;
    case 'Payments and settlement':
      return <PaymentsTab entity={entity} />;
    case 'Controls and exceptions':
      return <ControlsTab entity={entity} />;
    case 'Route assessment':
      return <RouteTab entity={entity} />;
    case 'Activity stream':
      return <ActivityTab entity={entity} />;
    case 'Data health':
      return <DataHealthTab entity={entity} />;
    case 'Service and SLA':
      return <ServiceTab entity={entity} />;
    default:
      return <SummaryTab entity={entity} />;
  }
}

/** The INV-1 and INV-2 decomposition, visible as a stacked bar that sums. */
function DecompositionBar({ entity }: { entity: Entity }) {
  const d = entity.decomposition;
  const total = d.total_cash.usd || 1;
  const segments = [
    { key: 'Deployable surplus', value: d.deployable_surplus.usd, colour: 'var(--ok-9)' },
    { key: 'Operating buffer', value: d.operating_buffer.usd, colour: 'var(--info-9)' },
    { key: 'Restricted', value: d.restricted.usd, colour: 'var(--warn-9)' },
  ];

  return (
    <div>
      <div
        className="flex h-6 w-full overflow-hidden rounded-[3px]"
        role="img"
        aria-label={`Cash decomposition: ${segments
          .map((s) => `${s.key} ${Math.round((s.value / total) * 100)} per cent`)
          .join(', ')}`}
      >
        {segments.map((segment) => (
          <div
            key={segment.key}
            title={`${segment.key}: ${Math.round((segment.value / total) * 100)}%`}
            style={{ width: `${(segment.value / total) * 100}%`, background: segment.colour }}
          />
        ))}
      </div>
      <ul className="mt-2 space-y-1">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-2 text-[11px]">
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-[1px]"
              style={{ background: segment.colour }}
            />
            <span className="flex-1 text-[var(--text-secondary)]">{segment.key}</span>
            <span className="tnum">
              {segment.key === 'Deployable surplus' ? (
                <Figure value={d.deployable_surplus} />
              ) : segment.key === 'Operating buffer' ? (
                <Figure value={d.operating_buffer} />
              ) : (
                <Figure value={d.restricted} />
              )}
            </span>
          </li>
        ))}
        <li className="flex items-center gap-2 border-t border-[var(--border-subtle)] pt-1 text-[11px] font-semibold">
          <span className="flex-1">Total cash</span>
          <span className="tnum">
            <Figure value={d.total_cash} />
          </span>
        </li>
      </ul>
      <p className="mt-2 text-[10px] leading-relaxed text-[var(--text-tertiary)]">{d.note}</p>
    </div>
  );
}

function SummaryTab({ entity }: { entity: Entity }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 rounded-[4px] bg-[var(--surface-3)] p-3">
        <Stat label="Functional currency" value={<span translate="no">{entity.functional_ccy}</span>} mono={false} />
        <Stat label="ERP" value={<span translate="no">{entity.erp_system}</span>} mono={false} />
        <Stat label="Ownership" value={pct(entity.ownership_pct / 100, 0)} />
        <Stat label="Country" value={entity.country_name} mono={false} />
        <Stat
          label="Onboarding"
          value={titleCase(entity.onboard_status)}
          mono={false}
          tone={entity.onboard_status === 'live' ? 'ok' : 'warn'}
        />
        <Stat
          label="Acquired"
          value={entity.acquired_on ? date(entity.acquired_on) : 'Organic'}
          mono={false}
        />
      </div>

      <Panel title="Cash decomposition" subtitle="INV-1 and INV-2">
        <div className="p-3">
          <DecompositionBar entity={entity} />
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-3">
        <Panel title="Funding">
          <div className="grid grid-cols-2 gap-3 p-3">
            <Stat label="Drawn" value={<Figure value={entity.drawn} />} />
            <Stat label="Committed" value={<Figure value={entity.committed} />} />
            <Stat label="Headroom" value={<Figure value={entity.headroom} />} tone="ok" />
            <Stat
              label="All-in rate"
              value={entity.all_in_rate !== null ? pct(entity.all_in_rate, 2) : 'no debt'}
            />
          </div>
        </Panel>
        <Panel title="Rates">
          <div className="grid grid-cols-2 gap-3 p-3">
            <Stat label="Deposit rate" value={pct(entity.deposit_rate, 2)} />
            <Stat
              label="Spread paid"
              value={
                entity.all_in_rate !== null
                  ? pct(entity.all_in_rate - entity.deposit_rate, 2)
                  : '—'
              }
              tone="err"
            />
            <Stat label="Pool status" value={titleCase(entity.pool_status)} mono={false} />
            <Stat label="Route" value={entity.route} />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function CashTab({ entity }: { entity: Entity }) {
  const accounts = useAccounts({ entity: entity.id });
  if (accounts.isPending) return <SkeletonRows rows={8} cols={5} />;
  if (accounts.error) return <ErrorState error={accounts.error} onRetry={() => accounts.refetch()} />;
  const rows = accounts.data ?? [];
  if (!rows.length) {
    return <EmptyState what="No accounts are recorded for this entity." owner="Local Coordinator" />;
  }

  return (
    <Panel
      title={`${rows.length} accounts`}
      subtitle={`${rows.filter((a) => a.feed_status === 'live').length} feeds current`}
    >
      <table className="grid-table dense">
        <thead>
          <tr>
            <th scope="col" className="freeze-col">Account</th>
            <th scope="col">Bank</th>
            <th scope="col">Purpose</th>
            <th scope="col">Feed</th>
            <th scope="col" className="num">Balance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((account) => (
            <tr key={account.id}>
              <td className="freeze-col ident">{account.iban_masked}</td>
              <td className="truncate" translate="no">{account.bank_name}</td>
              <td>
                <span className="flex items-center gap-1">
                  {titleCase(account.purpose)}
                  {account.is_restricted ? (
                    <Badge tone="warn" title={account.restriction_note ?? 'Restricted'}>
                      restricted
                    </Badge>
                  ) : null}
                </span>
              </td>
              <td>
                {account.feed_status === 'live' ? (
                  <span className="flex items-center gap-1 text-[var(--text-tertiary)]">
                    <Dot tone="ok" title="Feed current" />
                    <span translate="no">{account.feed_type}</span>
                  </span>
                ) : (
                  <StaleBadge
                    status={account.feed_status}
                    age={account.last_movement ? date(account.last_movement) : undefined}
                  />
                )}
              </td>
              <td className="num tnum">
                {account.balance ? <Figure value={account.balance} compact /> : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function ForecastTab({ entity }: { entity: Entity }) {
  const forecasts = useForecasts(entity.id);
  if (forecasts.isPending) return <SkeletonRows rows={8} cols={4} />;
  if (forecasts.error) return <ErrorState error={forecasts.error} onRetry={() => forecasts.refetch()} />;

  const forecast = forecasts.data?.[0];
  if (!forecast) {
    return (
      <EmptyState
        what={`No forecast cycle has been submitted for ${entity.short_name}.`}
        owner="Local Coordinator"
        action="Open the submission form"
        onAction={() => undefined}
      />
    );
  }

  const max = Math.max(...forecast.net_by_week.map((w) => Math.abs(w.usd)), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge
          tone={
            forecast.status === 'approved' ? 'ok' : forecast.status === 'challenged' ? 'warn' : 'info'
          }
        >
          {titleCase(forecast.status)}
        </Badge>
        <span className="text-[11px] text-[var(--text-tertiary)]">
          Cycle {forecast.cycle_year} week {forecast.cycle_week} · owner {forecast.owner}
        </span>
        {forecast.accuracy !== null ? (
          <span className="tnum ml-auto text-[11px]">
            Accuracy {pct(forecast.accuracy)}{' '}
            <span className="text-[var(--text-tertiary)]">on elapsed weeks</span>
          </span>
        ) : null}
      </div>

      <Panel title="Net position by week" subtitle="13-week horizon">
        <div className="flex h-[160px] items-end gap-1 p-3">
          {forecast.net_by_week.map((week, index) => {
            const height = Math.max(2, (Math.abs(week.usd) / max) * 120);
            const positive = week.usd >= 0;
            return (
              <div key={index} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                <div
                  title={`Week ${index}: ${positive ? 'inflow' : 'outflow'}`}
                  style={{
                    height,
                    background: positive ? 'var(--ok-9)' : 'var(--err-9)',
                  }}
                  className="w-full rounded-[1px]"
                />
                <span className="tnum text-[9px] text-[var(--text-tertiary)]">{index}</span>
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel title="Lines" subtitle={`${forecast.lines.length} rows`}>
        <table className="grid-table dense">
          <thead>
            <tr>
              <th scope="col" className="freeze-col">Week</th>
              <th scope="col">Category</th>
              <th scope="col" className="num">Forecast</th>
              <th scope="col" className="num">Actual</th>
              <th scope="col" className="num">Accuracy</th>
            </tr>
          </thead>
          <tbody>
            {forecast.lines.slice(0, 40).map((line) => (
              <tr key={`${line.week_offset}-${line.category}`}>
                <td className="freeze-col tnum">{line.week_offset}</td>
                <td>{titleCase(line.category)}</td>
                <td className="num tnum"><Figure value={line.amount} compact /></td>
                <td className="num tnum">
                  {line.actual ? <Figure value={line.actual} compact /> : '—'}
                </td>
                <td className="num tnum">
                  {line.accuracy !== null ? (
                    <span style={{ color: line.accuracy > 0.9 ? 'var(--ok-11)' : 'var(--warn-11)' }}>
                      {pct(line.accuracy)}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function PoolingTab({ entity }: { entity: Entity }) {
  const pools = usePools();
  const member = (pools.data ?? []).filter((pool) =>
    pool.members.some((m) => m.entity_id === entity.id),
  );

  return (
    <div className="space-y-3">
      <Panel title="Operating buffer" subtitle="structurally protected">
        <div className="p-3">
          <div className="flex items-baseline gap-2">
            <span className="tnum text-[20px] font-semibold text-[var(--info-11)]">
              <Figure value={entity.decomposition.operating_buffer} />
            </span>
            <Badge tone="info">never sweepable</Badge>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-secondary)]">
            This balance sits below the sweepable layer, not beside it. Pooling check 3 rejects any
            movement that would reach it, and LR12 blocks any workflow that includes it in a sweep.
            That is a structural guarantee, not a convention.
          </p>
        </div>
      </Panel>

      {pools.isPending ? (
        <SkeletonRows rows={4} cols={3} />
      ) : member.length === 0 ? (
        <EmptyState
          what={`${entity.short_name} is not a member of any pool.`}
          owner="Group Treasurer"
        />
      ) : (
        member.map((pool) => (
          <Panel key={pool.id} title={pool.name} subtitle={titleCase(pool.status)}>
            <div className="space-y-2 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <RouteBadge route={pool.route} />
                <Badge tone="neutral">{titleCase(pool.kind)}</Badge>
                <Badge tone={pool.legal_cleared_by ? 'ok' : 'warn'}>
                  {pool.legal_cleared_by ? 'legal cleared' : 'legal pending'}
                </Badge>
                <Badge tone={pool.tax_cleared_by ? 'ok' : 'warn'}>
                  {pool.tax_cleared_by ? 'tax cleared' : 'tax pending'}
                </Badge>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)]">
                {pool.route_detail.mechanism}
              </p>
              <p className="text-[11px] text-[var(--text-tertiary)]">
                Binding constraint: {pool.route_detail.binding_constraint}
              </p>
            </div>
          </Panel>
        ))
      )}
    </div>
  );
}

function FundingTab({ entity }: { entity: Entity }) {
  const facilities = useFacilities();
  const rows = (facilities.data ?? []).filter((f) => f.entity_id === entity.id);

  if (facilities.isPending) return <SkeletonRows rows={5} cols={5} />;
  if (!rows.length) {
    return (
      <EmptyState
        what={`${entity.short_name} carries no debt facility.`}
        owner="Group Treasurer"
      />
    );
  }

  return (
    <Panel title="Facilities" subtitle={`${rows.length} recorded`}>
      <table className="grid-table dense">
        <thead>
          <tr>
            <th scope="col" className="freeze-col">Facility</th>
            <th scope="col">Bank</th>
            <th scope="col">Kind</th>
            <th scope="col" className="num">Drawn</th>
            <th scope="col" className="num">Headroom</th>
            <th scope="col" className="num">All-in</th>
            <th scope="col">Maturity</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((facility) => (
            <tr key={facility.id}>
              <td className="freeze-col ident">{facility.id}</td>
              <td className="truncate" translate="no">{facility.bank_name}</td>
              <td>{titleCase(facility.kind)}</td>
              <td className="num tnum"><Figure value={facility.drawn} compact /></td>
              <td className="num tnum"><Figure value={facility.headroom} compact /></td>
              <td className="num tnum">{pct(facility.all_in_rate, 2)}</td>
              <td className="tnum">{date(facility.maturity)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.some((f) => f.covenant_note) ? (
        <div className="border-t border-[var(--border-subtle)] p-3">
          <p className="text-[10px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
            Covenants
          </p>
          {rows
            .filter((f) => f.covenant_note)
            .map((f) => (
              <p key={f.id} className="mt-1 text-[11px] text-[var(--text-secondary)]">
                <span className="ident">{f.id}</span> · {f.covenant_note}
              </p>
            ))}
        </div>
      ) : null}
    </Panel>
  );
}

function InvestmentsTab({ entity }: { entity: Entity }) {
  const accounts = useAccounts({ entity: entity.id });
  const investments = (accounts.data ?? []).filter((a) => a.purpose === 'investment');

  return (
    <div className="space-y-3">
      <Panel title="Deployable surplus" subtitle="what may be invested or lent">
        <div className="grid grid-cols-2 gap-3 p-3">
          <Stat
            label="Deployable surplus"
            value={<Figure value={entity.decomposition.deployable_surplus} />}
            tone="ok"
          />
          <Stat label="Deposit rate earned" value={pct(entity.deposit_rate, 2)} />
          <Stat
            label="Annual return at that rate"
            value={
              <UsdFigure usd={entity.decomposition.deployable_surplus.usd * entity.deposit_rate} />
            }
          />
          <Stat
            label="Group cost of that cash"
            value={
              entity.all_in_rate !== null ? (
                <UsdFigure
                  usd={entity.decomposition.deployable_surplus.usd * entity.all_in_rate}
                />
              ) : (
                '—'
              )
            }
            tone="err"
          />
        </div>
      </Panel>

      {accounts.isPending ? (
        <SkeletonRows rows={3} cols={3} />
      ) : investments.length === 0 ? (
        <EmptyState
          what={`${entity.short_name} holds no dedicated investment account.`}
          owner="Group Treasurer"
        />
      ) : (
        <Panel title="Investment accounts">
          <table className="grid-table dense">
            <thead>
              <tr>
                <th scope="col" className="freeze-col">Account</th>
                <th scope="col">Bank</th>
                <th scope="col" className="num">Balance</th>
              </tr>
            </thead>
            <tbody>
              {investments.map((account) => (
                <tr key={account.id}>
                  <td className="freeze-col ident">{account.iban_masked}</td>
                  <td translate="no">{account.bank_name}</td>
                  <td className="num tnum">
                    {account.balance ? <Figure value={account.balance} compact /> : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}

function ExposuresTab({ entity }: { entity: Entity }) {
  const exposures = useExposures(entity.id);
  if (exposures.isPending) return <SkeletonRows rows={4} cols={4} />;
  const rows = exposures.data ?? [];
  if (!rows.length) return <EmptyState what="No exposures recorded." owner="Risk and Control" />;

  return (
    <Panel title="Exposures" subtitle={`${rows.length} positions`}>
      <table className="grid-table dense">
        <thead>
          <tr>
            <th scope="col" className="freeze-col">Kind</th>
            <th scope="col">Pair</th>
            <th scope="col" className="num">Notional</th>
            <th scope="col" className="num">Hedged</th>
            <th scope="col" className="num">Unhedged</th>
            <th scope="col" className="num">Ratio</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((exposure) => (
            <tr key={exposure.id}>
              <td className="freeze-col">{titleCase(exposure.kind)}</td>
              <td className="ident" translate="no">{exposure.currency_pair ?? '—'}</td>
              <td className="num tnum"><UsdFigure usd={exposure.notional_usd} compact /></td>
              <td className="num tnum"><UsdFigure usd={exposure.hedged_usd} compact /></td>
              <td className="num tnum"><UsdFigure usd={exposure.unhedged_usd} compact /></td>
              <td className="num tnum">
                <span
                  style={{
                    color: exposure.hedge_ratio >= 0.8 ? 'var(--ok-11)' : 'var(--warn-11)',
                  }}
                >
                  {pct(exposure.hedge_ratio)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function PaymentsTab({ entity }: { entity: Entity }) {
  const accounts = useAccounts({ entity: entity.id });
  const rows = useMemo(() => accounts.data ?? [], [accounts.data]);
  const byConnectivity = useMemo(() => {
    const map = new Map<string, number>();
    for (const account of rows) map.set(account.feed_type, (map.get(account.feed_type) ?? 0) + 1);
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  return (
    <div className="space-y-3">
      <Panel title="Settlement readiness">
        <div className="p-3">
          <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
            This control layer never initiates a payment. It records a settlement instruction and
            the independent holder who performed it, so that LR4 can be demonstrated rather than
            asserted. Execution stays in the bank channel.
          </p>
        </div>
      </Panel>
      <Panel title="Channel mix" subtitle={`${rows.length} accounts`}>
        <ul className="p-3">
          {byConnectivity.map(([channel, number]) => (
            <li key={channel} className="flex items-center gap-2 py-1 text-[11px]">
              <span className="w-[88px] shrink-0 ident" translate="no">{channel}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-4)]">
                <div
                  className="h-full rounded-full bg-[var(--info-9)]"
                  style={{ width: `${(number / Math.max(rows.length, 1)) * 100}%` }}
                />
              </div>
              <span className="tnum w-6 shrink-0 text-right">{number}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function ControlsTab({ entity }: { entity: Entity }) {
  const audit = useAudit({ object_kind: 'entity', object_id: entity.id, limit: '25' });
  return (
    <div className="space-y-3">
      <Panel title="Capability separation">
        <div className="p-3 text-[11px] leading-relaxed text-[var(--text-secondary)]">
          <p>
            Initiation, approval and settlement are held by different personas. The browser hides
            the controls a persona lacks, and the API rejects the call regardless. Hiding alone is
            not a control.
          </p>
        </div>
      </Panel>
      <Panel title="Exceptions raised against this entity">
        {audit.isPending ? (
          <SkeletonRows rows={5} cols={3} dense />
        ) : (audit.data ?? []).length === 0 ? (
          <EmptyState what="No exceptions have been raised against this entity." />
        ) : (
          <table className="grid-table dense">
            <thead>
              <tr>
                <th scope="col" className="freeze-col">Seq</th>
                <th scope="col">Action</th>
                <th scope="col">Actor</th>
                <th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {(audit.data ?? []).map((event) => (
                <tr key={event.seq}>
                  <td className="freeze-col ident">{event.seq}</td>
                  <td className="ident">{event.action}</td>
                  <td>{event.actor_name}</td>
                  <td className="tnum">{dateTime(event.ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

/**
 * Route assessment. This replaces v1's invented "LOC-1 Assessment Matrix" with
 * the entity's actual Route A to D classification and the authority behind it.
 */
function RouteTab({ entity }: { entity: Entity }) {
  const routes = useRoutes();
  const notional = useNotionalPooling();
  const route = (routes.data ?? []).find((r) => r.code === entity.route);

  return (
    <div className="space-y-3">
      <Panel title={`Route ${entity.route}`} subtitle={route?.name}>
        <div className="space-y-2 p-3">
          <p className="text-[12px] text-[var(--text-primary)]">{route?.mechanism}</p>
          <p className="text-[11px] text-[var(--text-secondary)]">
            <strong className="font-medium">Binding constraint:</strong>{' '}
            {route?.binding_constraint}
          </p>
          <p className="text-[11px] text-[var(--text-tertiary)]">
            Scope: {route?.scope} ·{' '}
            {route?.permits_movement ? 'movement is available' : 'no movement is available'}
          </p>
          {route?.citations.length ? (
            <ul className="mt-2 space-y-1.5">
              {route.citations.map((citation) => (
                <li
                  key={citation.reference}
                  className="rounded-[3px] bg-[var(--surface-3)] p-2 text-[11px]"
                >
                  <p className="font-medium text-[var(--text-primary)]" translate="no">
                    {citation.authority}
                  </p>
                  <p className="ident text-[10px] text-[var(--text-tertiary)]">
                    {citation.reference}
                  </p>
                  <p className="mt-0.5 text-[var(--text-secondary)]">{citation.effect}</p>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </Panel>

      {entity.country_iso2 === 'IN' && notional.data ? (
        <Panel title="Notional pooling" subtitle="stated precisely">
          <div className="space-y-2 p-3">
            <p className="text-[12px] text-[var(--text-primary)]">{notional.data.statement}</p>
            <ul className="space-y-1.5">
              {notional.data.citations.map((citation) => (
                <li key={citation.reference} className="text-[11px]">
                  <span className="ident text-[var(--text-tertiary)]">{citation.reference}</span>{' '}
                  — {citation.effect}
                </li>
              ))}
            </ul>
            <div
              className="mt-2 rounded-[3px] p-2 text-[11px] leading-relaxed"
              style={{ background: 'var(--warn-3)', boxShadow: 'inset 0 0 0 1px var(--warn-9)' }}
            >
              <p className="font-medium text-[var(--text-primary)]">GIFT City</p>
              <p className="mt-0.5 text-[var(--text-secondary)]">{notional.data.gift_city_caveat}</p>
            </div>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

function ActivityTab({ entity }: { entity: Entity }) {
  const audit = useAudit({ object_id: entity.id, limit: '40' });
  if (audit.isPending) return <SkeletonRows rows={10} cols={3} dense />;
  const rows = audit.data ?? [];
  if (!rows.length) return <EmptyState what="No activity recorded for this entity yet." />;

  return (
    <ol className="space-y-1.5">
      {rows.map((event) => (
        <li key={event.seq} className="rounded-[3px] bg-[var(--surface-3)] p-2">
          <div className="flex items-center gap-2 text-[11px]">
            <span className="ident text-[var(--text-tertiary)]">#{event.seq}</span>
            <span className="ident font-medium">{event.action}</span>
            <span className="ml-auto tnum text-[10px] text-[var(--text-tertiary)]">
              {dateTime(event.ts)}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">{event.detail}</p>
          <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
            {event.actor_name} ({event.actor_persona})
            {event.justification ? ` · ${event.justification}` : ''}
          </p>
        </li>
      ))}
    </ol>
  );
}

function DataHealthTab({ entity }: { entity: Entity }) {
  const accounts = useAccounts({ entity: entity.id });
  const rows = accounts.data ?? [];
  const degraded = rows.filter((a) => a.feed_status !== 'live');

  return (
    <div className="space-y-3">
      <Panel title="Feed coverage">
        <div className="p-3">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Accounts" value={entity.account_count} />
            <Stat label="Current" value={entity.live_accounts} tone="ok" />
            <Stat
              label="Stale or offline"
              value={entity.stale_accounts + entity.offline_accounts}
              tone={entity.stale_accounts + entity.offline_accounts ? 'warn' : 'neutral'}
            />
          </div>
          <CoverageNote
            className="mt-3"
            coverage={{
              accounts_total: entity.account_count,
              accounts_current: entity.live_accounts,
              pct: entity.coverage_pct,
              statement: `${entity.live_accounts} of ${entity.account_count} accounts current`,
            }}
          />
        </div>
      </Panel>

      {degraded.length ? (
        <Panel title="Degraded feeds" subtitle="shown, never hidden">
          <table className="grid-table dense">
            <thead>
              <tr>
                <th scope="col" className="freeze-col">Account</th>
                <th scope="col">Bank</th>
                <th scope="col">Status</th>
                <th scope="col">Last movement</th>
              </tr>
            </thead>
            <tbody>
              {degraded.map((account) => (
                <tr key={account.id}>
                  <td className="freeze-col ident">{account.iban_masked}</td>
                  <td translate="no">{account.bank_name}</td>
                  <td><StaleBadge status={account.feed_status} /></td>
                  <td className="tnum">
                    {account.last_movement ? date(account.last_movement) : 'never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-[var(--border-subtle)] p-3 text-[11px] text-[var(--text-tertiary)]">
            An offline account's last known value still contributes to this entity's own view but
            is excluded from the group aggregate, and that exclusion is stated on the aggregate.
          </p>
        </Panel>
      ) : (
        <EmptyState what="Every feed for this entity is current." />
      )}
    </div>
  );
}

function ServiceTab({ entity }: { entity: Entity }) {
  const onboarding = useOnboarding(entity.id);
  const [open, setOpen] = useState(true);

  return (
    <div className="space-y-3">
      <Panel title="SLA attainment" subtitle="derived from feed currency">
        <div className="p-3">
          <div className="flex items-baseline gap-2">
            <span className="tnum text-[24px] font-semibold">{pct(entity.coverage_pct)}</span>
            <Badge tone={entity.coverage_pct >= 0.95 ? 'ok' : 'warn'}>
              {entity.coverage_pct >= 0.95 ? 'on target' : 'below target'}
            </Badge>
          </div>
          <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
            A hub cannot answer within its service window on a balance it does not have, so
            attainment is computed from feed currency rather than recorded separately.
          </p>
        </div>
      </Panel>

      <Panel
        title="Day-1 kit"
        subtitle="seven items"
        actions={
          <Button variant="ghost" onClick={() => setOpen((value) => !value)}>
            {open ? 'Collapse' : 'Expand'}
          </Button>
        }
      >
        {open ? (
          onboarding.isPending ? (
            <SkeletonRows rows={7} cols={3} dense />
          ) : (
            <table className="grid-table dense">
              <thead>
                <tr>
                  <th scope="col" className="freeze-col">#</th>
                  <th scope="col">Item</th>
                  <th scope="col">Owner</th>
                  <th scope="col" className="num">Due day</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {(onboarding.data ?? []).map((item) => (
                  <tr key={item.item_no}>
                    <td className="freeze-col tnum">{item.item_no}</td>
                    <td>{item.item}</td>
                    <td>{item.owner}</td>
                    <td className="num tnum">{item.due_day}</td>
                    <td>
                      <Badge
                        tone={
                          item.status === 'done'
                            ? 'ok'
                            : item.status === 'blocked'
                              ? 'err'
                              : item.status === 'in_progress'
                                ? 'info'
                                : 'neutral'
                        }
                      >
                        {titleCase(item.status)}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
      </Panel>
    </div>
  );
}
