/**
 * COCKPIT — the single-entity scoped view.
 *
 * The local coordinator's answer to "what does the centre actually see about
 * me?" is the raw group payload, unedited. A local coordinator who believes
 * the centre can take their payroll float will pad their forecast; the only
 * durable fix is to remove the asymmetry.
 */

import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import { Lock, ShieldCheck } from 'lucide-react';
import { useAppState, useEntities, useEntity, useGroupView, useOnboarding } from '@/lib/hooks';
import { Badge, Button, Panel, RouteBadge, Stat } from '@/components/primitives';
import { CoverageNote, EmptyState, ErrorState, SkeletonRows } from '@/components/states';
import { Figure } from '@/components/Figure';
import { date, pct, titleCase } from '@/lib/format';

export function Cockpit() {
  const { entityId } = useParams();
  const navigate = useNavigate();
  const state = useAppState();
  const entities = useEntities();

  // A persona scoped to one entity lands on its own entity, always.
  const persona = state.data?.persona;
  const target =
    entityId ?? (persona?.scope_kind === 'entity' ? persona.scope_ref : null) ?? entities.data?.[0]?.id;

  const entity = useEntity(target ?? null);
  const groupView = useGroupView(target ?? null);
  const onboarding = useOnboarding(target ?? null);
  const [showRaw, setShowRaw] = useState(false);

  if (!target) {
    if (entities.isPending) return <SkeletonRows rows={8} cols={4} />;
    return <EmptyState what="No entity is in scope for this persona." />;
  }
  if (entity.error) return <ErrorState error={entity.error} onRetry={() => entity.refetch()} />;
  if (entity.isPending || !entity.data) return <SkeletonRows rows={10} cols={4} />;

  const data = entity.data;

  return (
    <div tabIndex={0} aria-label="Local cockpit" className="h-full overflow-auto p-3">
      <div className="mx-auto max-w-[1100px] space-y-3">
        <header className="flex flex-wrap items-center gap-2">
          <h1 className="text-[20px] font-semibold" translate="no">
            {data.short_name}
          </h1>
          <RouteBadge route={data.route} />
          <Badge tone={data.onboard_status === 'live' ? 'ok' : 'warn'}>
            {titleCase(data.onboard_status)}
          </Badge>
          <span className="text-[12px] text-[var(--text-tertiary)]" translate="no">
            {data.legal_name} · {data.country_name}
          </span>
          <label htmlFor="cockpit-entity" className="sr-only">
            Entity
          </label>
          <select
            id="cockpit-entity"
            value={target}
            onChange={(event) => navigate(`/cockpit/${event.target.value}`)}
            disabled={persona?.scope_kind === 'entity'}
            title={
              persona?.scope_kind === 'entity'
                ? 'Your persona is scoped to a single entity.'
                : 'Switch entity'
            }
            className="ml-auto h-7 rounded-[3px] px-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)] disabled:opacity-50"
          >
            {(entities.data ?? []).map((option) => (
              <option key={option.id} value={option.id}>
                {option.short_name}
              </option>
            ))}
          </select>
        </header>

        {/* The buffer promise, made structural rather than cultural. */}
        <Panel
          title="Your operating buffer"
          subtitle="structurally protected"
          actions={<Badge tone="info">never sweepable</Badge>}
        >
          <div className="flex flex-wrap items-start gap-6 p-4">
            <div>
              <Stat
                label="Protected operating buffer"
                value={<Figure value={data.decomposition.operating_buffer} />}
                tone="info"
              />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start gap-2">
                <Lock size={14} className="mt-0.5 shrink-0 text-[var(--info-11)]" aria-hidden />
                <p className="text-[12px] leading-relaxed text-[var(--text-secondary)]">
                  This balance is not merely excluded from the sweep calculation; it sits beneath
                  the sweepable layer. Pooling check 3 rejects any proposal that would reach it and
                  names the shortfall in the rejection. LR12 blocks any workflow design that
                  includes it in a sweep, and the linter will not pass that design.{' '}
                  <strong className="font-medium text-[var(--text-primary)]">
                    The centre cannot take it, by construction.
                  </strong>
                </p>
              </div>
            </div>
          </div>
        </Panel>

        <div className="grid grid-cols-2 gap-3">
          <Panel title="Your position">
            <div className="grid grid-cols-2 gap-4 p-3">
              <Stat label="Total cash" value={<Figure value={data.decomposition.total_cash} />} />
              <Stat
                label="Available local"
                value={<Figure value={data.decomposition.available_local} />}
              />
              <Stat
                label="Deployable surplus"
                value={<Figure value={data.decomposition.deployable_surplus} />}
                tone="ok"
                sub="A subset of available local cash, never an addition to it"
              />
              <Stat
                label="Restricted"
                value={<Figure value={data.decomposition.restricted} />}
                tone="warn"
              />
            </div>
          </Panel>

          <Panel title="Your data quality">
            <div className="grid grid-cols-2 gap-4 p-3">
              <Stat label="Accounts" value={data.account_count} />
              <Stat label="Feeds current" value={data.live_accounts} tone="ok" />
              <Stat
                label="Stale"
                value={data.stale_accounts}
                tone={data.stale_accounts ? 'warn' : 'neutral'}
              />
              <Stat
                label="Offline"
                value={data.offline_accounts}
                tone={data.offline_accounts ? 'err' : 'neutral'}
              />
            </div>
            <div className="border-t border-[var(--border-subtle)] px-3 py-2">
              <CoverageNote
                coverage={{
                  accounts_total: data.account_count,
                  accounts_current: data.live_accounts,
                  pct: data.coverage_pct,
                  statement: `${data.live_accounts} of ${data.account_count} accounts current`,
                }}
              />
            </div>
          </Panel>
        </div>

        {/* "What the group sees about me" — byte-for-byte, no summarisation. */}
        <Panel
          title="What the group sees about you"
          subtitle="the exact payload the CFO receives"
          actions={
            <Button variant="ghost" onClick={() => setShowRaw((value) => !value)}>
              {showRaw ? 'Hide raw payload' : 'Show raw payload'}
            </Button>
          }
        >
          <div className="p-3">
            <div className="flex items-start gap-2">
              <ShieldCheck size={14} className="mt-0.5 shrink-0 text-[var(--ok-11)]" aria-hidden />
              <p className="text-[12px] leading-relaxed text-[var(--text-secondary)]">
                {groupView.data?.note ??
                  'This payload is produced by the same function that serves the CFO.'}{' '}
                Nothing is summarised, withheld or restated for this view. A test in the suite
                asserts the two payloads are byte-identical.
              </p>
            </div>

            {showRaw ? (
              groupView.isPending ? (
                <SkeletonRows rows={10} cols={2} dense />
              ) : groupView.error ? (
                <ErrorState error={groupView.error} onRetry={() => groupView.refetch()} />
              ) : (
                <pre
                  tabIndex={0}
                  aria-label="Raw group-view payload"
                  className="ident mt-3 max-h-[420px] overflow-auto rounded-[3px] bg-[var(--surface-1)] p-3 text-[11px] leading-relaxed text-[var(--text-secondary)]"
                >
                  {JSON.stringify(groupView.data?.entity, null, 2)}
                </pre>
              )
            ) : null}
          </div>
        </Panel>

        <Panel title="Your Day-1 kit" subtitle="seven items">
          {onboarding.isPending ? (
            <SkeletonRows rows={7} cols={4} />
          ) : (
            <table className="grid-table">
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
          )}
        </Panel>

        <footer className="pb-4 text-[11px] text-[var(--text-tertiary)]">
          Deposit rate {pct(data.deposit_rate, 2)}
          {data.all_in_rate !== null ? ` · borrowing at ${pct(data.all_in_rate, 2)}` : ''} ·{' '}
          {data.acquired_on ? `acquired ${date(data.acquired_on)}` : 'organic'} ·{' '}
          <span translate="no">{data.erp_system}</span>
        </footer>
      </div>
    </div>
  );
}
