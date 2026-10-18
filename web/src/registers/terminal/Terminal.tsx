/**
 * TERMINAL — the operations console.
 *
 * Liquidity meters, the work queue, the deal and settlement blotters, and the
 * kernel log with chain verification. Every percentage here is computed from
 * the API; the grep test fails the build if a literal ever appears.
 */

import { useState } from 'react';
import { useQueryState } from 'nuqs';
import { CheckCircle2, Link2Off, ShieldCheck, Signature } from 'lucide-react';
import {
  useAppState,
  useAudit,
  useChain,
  useDecideProposal,
  useEntities,
  useKpis,
  useProposals,
} from '@/lib/hooks';
import { Badge, Button, Dot, Field, Panel, Stat, cn } from '@/components/primitives';
import { CoverageNote, EmptyState, ErrorState, SkeletonRows } from '@/components/states';
import { Figure, UsdFigure } from '@/components/Figure';
import { dateTime, pct, titleCase, truncate } from '@/lib/format';
import type { Proposal } from '@/lib/types';

const VIEWS = ['dashboard', 'queue', 'blotters', 'kernel'] as const;

export function Terminal() {
  const [view, setView] = useQueryState('view', { defaultValue: 'dashboard' });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav
        role="tablist"
        aria-label="Terminal views"
        className="flex shrink-0 gap-1 border-b border-[var(--border-subtle)] bg-[var(--surface-2)] px-2 py-1.5"
      >
        {VIEWS.map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={view === name}
            onClick={() => void setView(name)}
            className={cn(
              'h-7 rounded-[3px] px-2.5 text-[12px] transition-colors duration-100',
              view === name
                ? 'bg-[var(--surface-4)] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--border-interactive)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
            )}
          >
            {titleCase(name)}
          </button>
        ))}
      </nav>

      <div
        role="tabpanel"
        tabIndex={0}
        aria-label={`Terminal: ${view}`}
        className="min-h-0 flex-1 overflow-auto p-2"
      >
        {view === 'dashboard' ? (
          <Dashboard />
        ) : view === 'queue' ? (
          <WorkQueue />
        ) : view === 'blotters' ? (
          <Blotters />
        ) : (
          <KernelLog />
        )}
      </div>
    </div>
  );
}

function Dashboard() {
  const state = useAppState();
  const entities = useEntities();
  const kpis = useKpis();

  if (state.isPending || entities.isPending) return <SkeletonRows rows={10} cols={5} />;
  const summary = state.data?.summary;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-2">
        {(kpis.data ?? []).slice(0, 4).map((kpi) => (
          <Panel key={kpi.code}>
            <div className="p-3">
              <p className="truncate text-[10px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
                {kpi.label}
              </p>
              <p
                className="tnum mt-1 text-[22px] leading-none font-bold"
                style={{ color: kpi.on_target ? 'var(--ok-11)' : 'var(--warn-11)' }}
              >
                {kpi.unit === 'pct' ? (
                  pct(kpi.value)
                ) : kpi.unit === 'usd' ? (
                  <UsdFigure usd={kpi.value} compact />
                ) : (
                  Math.round(kpi.value)
                )}
              </p>
              <p className="mt-1 truncate text-[10px] text-[var(--text-tertiary)]">{kpi.source}</p>
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="Liquidity meters" subtitle="every figure computed from the API">
        <table className="grid-table dense">
          <thead>
            <tr>
              <th scope="col" className="freeze-col">Entity</th>
              <th scope="col" style={{ width: '34%' }}>Decomposition</th>
              <th scope="col" className="num">Deployable</th>
              <th scope="col" className="num">Buffer</th>
              <th scope="col" className="num">Drawn</th>
              <th scope="col" className="num">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {(entities.data ?? []).map((entity) => {
              const d = entity.decomposition;
              const total = d.total_cash.usd || 1;
              return (
                <tr key={entity.id}>
                  <td className="freeze-col">
                    <span className="flex items-center gap-1.5">
                      <Dot
                        tone={entity.coverage_pct === 1 ? 'ok' : 'warn'}
                        title={`${entity.live_accounts} of ${entity.account_count} feeds current`}
                      />
                      <span className="truncate" translate="no">{entity.short_name}</span>
                    </span>
                  </td>
                  <td>
                    <div
                      className="flex h-2.5 w-full overflow-hidden rounded-[2px]"
                      role="img"
                      aria-label={`${entity.short_name}: deployable ${pct(d.deployable_surplus.usd / total, 0)}, buffer ${pct(d.operating_buffer.usd / total, 0)}, restricted ${pct(d.restricted.usd / total, 0)}`}
                    >
                      <div
                        style={{ width: `${(d.deployable_surplus.usd / total) * 100}%`, background: 'var(--ok-9)' }}
                        title="Deployable surplus"
                      />
                      <div
                        style={{ width: `${(d.operating_buffer.usd / total) * 100}%`, background: 'var(--info-9)' }}
                        title="Operating buffer, never sweepable"
                      />
                      <div
                        style={{ width: `${(d.restricted.usd / total) * 100}%`, background: 'var(--warn-9)' }}
                        title="Restricted"
                      />
                    </div>
                  </td>
                  <td className="num tnum"><Figure value={d.deployable_surplus} compact /></td>
                  <td className="num tnum"><Figure value={d.operating_buffer} compact /></td>
                  <td className="num tnum"><Figure value={entity.drawn} compact /></td>
                  <td className="num tnum">{pct(entity.coverage_pct, 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {summary ? (
          <div className="border-t border-[var(--border-subtle)] px-3 py-1.5">
            <CoverageNote coverage={summary.coverage} />
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

function WorkQueue() {
  const proposals = useProposals();
  const state = useAppState();
  const approve = useDecideProposal('approve');
  const settle = useDecideProposal('settle');
  const [justification, setJustification] = useState('');
  const [acting, setActing] = useState<string | null>(null);

  if (proposals.isPending) return <SkeletonRows rows={8} cols={6} />;
  if (proposals.error) return <ErrorState error={proposals.error} onRetry={() => proposals.refetch()} />;

  const persona = state.data?.persona;
  const pending = (proposals.data ?? []).filter((p) =>
    ['pending_auth', 'authorised', 'checks_failed'].includes(p.status),
  );

  if (!pending.length) {
    return <EmptyState what="Nothing is awaiting a decision." owner="Group Treasurer" />;
  }

  return (
    <div className="space-y-2">
      {pending.map((proposal) => {
        const isApproval = proposal.status === 'pending_auth';
        const isSettlement = proposal.status === 'authorised';
        const canAct =
          (isApproval && persona?.can_approve) || (isSettlement && persona?.can_settle);
        // LR1 and LR4 are enforced on the server; the UI states the same rule so
        // the reader understands why the control is unavailable.
        const selfApproval = isApproval && proposal.created_by === persona?.id;
        const selfSettlement =
          isSettlement &&
          (proposal.created_by === persona?.id || proposal.approved_by === persona?.id);
        const mutation = isApproval ? approve : settle;
        const open = acting === proposal.id;

        return (
          <Panel
            key={proposal.id}
            title={`${proposal.id} · ${titleCase(proposal.kind)}`}
            subtitle={`${proposal.source_entity_id} → ${proposal.target_entity_id}`}
            actions={
              <Badge
                tone={
                  proposal.status === 'checks_failed'
                    ? 'err'
                    : proposal.status === 'authorised'
                      ? 'info'
                      : 'warn'
                }
              >
                {titleCase(proposal.status)}
              </Badge>
            }
          >
            <div className="grid grid-cols-5 gap-4 p-3">
              <Stat label="Amount" value={<Figure value={proposal.amount} compact />} />
              <Stat label="Rate" value={pct(proposal.interest_rate, 2)} />
              <Stat label="Tenor" value={`${proposal.tenor_days} days`} />
              <Stat label="Route" value={proposal.route} />
              <Stat
                label="Checks"
                value={`${proposal.checks.length - proposal.blocking_count - proposal.warning_count}/${proposal.checks.length}`}
                tone={proposal.blocking_count ? 'err' : proposal.warning_count ? 'warn' : 'ok'}
                sub={`${proposal.blocking_count} blocking · ${proposal.warning_count} warning`}
              />
            </div>

            <div className="border-t border-[var(--border-subtle)] px-3 py-2 text-[11px] text-[var(--text-tertiary)]">
              Created by <span className="ident">{proposal.created_by}</span>
              {proposal.approved_by ? (
                <>
                  {' '}· approved by <span className="ident">{proposal.approved_by}</span>
                </>
              ) : null}
              {proposal.settled_by ? (
                <>
                  {' '}· settled by <span className="ident">{proposal.settled_by}</span>
                </>
              ) : null}
            </div>

            {proposal.status !== 'checks_failed' ? (
              <div className="border-t border-[var(--border-subtle)] p-3">
                {selfApproval || selfSettlement ? (
                  <p
                    className="rounded-[3px] p-2 text-[11px]"
                    style={{ background: 'var(--warn-3)', color: 'var(--text-primary)' }}
                  >
                    {selfApproval
                      ? 'LR1: you created this proposal and cannot approve it. The API rejects the call as well as the button being unavailable.'
                      : 'LR4: settlement must be independent of both initiation and approval.'}
                  </p>
                ) : !canAct ? (
                  <p className="text-[11px] text-[var(--text-tertiary)]">
                    {persona?.display_name} holds no{' '}
                    {isApproval ? 'approve' : 'settle'} capability. This is enforced server-side.
                  </p>
                ) : open ? (
                  <form
                    className="space-y-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (justification.trim().length < 4) return;
                      mutation.mutate(
                        { id: proposal.id, justification: justification.trim() },
                        {
                          onSuccess: () => {
                            setActing(null);
                            setJustification('');
                          },
                        },
                      );
                    }}
                  >
                    <Field
                      label={isApproval ? 'Approval justification' : 'Settlement justification'}
                      htmlFor={`just-${proposal.id}`}
                      hint="LR7: recorded immutably against this proposal."
                      error={
                        justification.length > 0 && justification.trim().length < 4
                          ? 'At least four characters.'
                          : null
                      }
                    >
                      <textarea
                        id={`just-${proposal.id}`}
                        value={justification}
                        onChange={(event) => setJustification(event.target.value)}
                        required
                        minLength={4}
                        maxLength={500}
                        rows={2}
                        className="resize-none rounded-[3px] bg-[var(--surface-1)] p-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
                      />
                    </Field>
                    {mutation.error ? <ErrorState error={mutation.error} /> : null}
                    <div className="flex gap-2">
                      <Button
                        type="submit"
                        variant="primary"
                        disabled={justification.trim().length < 4 || mutation.isPending}
                      >
                        <Signature size={12} aria-hidden />
                        {mutation.isPending
                          ? 'Recording…'
                          : isApproval
                            ? 'Confirm approval'
                            : 'Confirm settlement'}
                      </Button>
                      <Button variant="ghost" onClick={() => setActing(null)}>
                        Cancel
                      </Button>
                    </div>
                  </form>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setActing(proposal.id);
                      setJustification('');
                    }}
                  >
                    {isApproval ? 'Approve…' : 'Settle…'}
                  </Button>
                )}
              </div>
            ) : (
              <div className="border-t border-[var(--border-subtle)] p-3">
                <p className="text-[11px] text-[var(--err-11)]">
                  {proposal.checks
                    .filter((check) => check.result === 'ERR')
                    .map((check) => `[${check.code}] ${check.detail}`)
                    .join(' ')}
                </p>
              </div>
            )}
          </Panel>
        );
      })}
    </div>
  );
}

function Blotters() {
  const proposals = useProposals();
  if (proposals.isPending) return <SkeletonRows rows={10} cols={7} />;
  const rows = proposals.data ?? [];

  const groups: { title: string; filter: (p: Proposal) => boolean }[] = [
    { title: 'Deal blotter', filter: (p) => ['pending_auth', 'authorised'].includes(p.status) },
    { title: 'Settlement blotter', filter: (p) => p.status === 'settled' },
    { title: 'Rejected and failed', filter: (p) => ['rejected', 'checks_failed'].includes(p.status) },
  ];

  return (
    <div className="space-y-2">
      {groups.map((group) => {
        const subset = rows.filter(group.filter);
        return (
          <Panel key={group.title} title={group.title} subtitle={`${subset.length} rows`}>
            {subset.length === 0 ? (
              <EmptyState what={`Nothing in the ${group.title.toLowerCase()}.`} />
            ) : (
              <table className="grid-table dense">
                <thead>
                  <tr>
                    <th scope="col" className="freeze-col">Ref</th>
                    <th scope="col">Kind</th>
                    <th scope="col">Source</th>
                    <th scope="col">Target</th>
                    <th scope="col" className="num">Amount</th>
                    <th scope="col" className="num">Rate</th>
                    <th scope="col">Route</th>
                    <th scope="col">Created</th>
                    <th scope="col">Approved</th>
                    <th scope="col">Settled</th>
                  </tr>
                </thead>
                <tbody>
                  {subset.map((proposal) => (
                    <tr key={proposal.id}>
                      <td className="freeze-col ident">{proposal.id}</td>
                      <td>{titleCase(proposal.kind)}</td>
                      <td className="ident">{proposal.source_entity_id}</td>
                      <td className="ident">{proposal.target_entity_id}</td>
                      <td className="num tnum"><Figure value={proposal.amount} compact /></td>
                      <td className="num tnum">{pct(proposal.interest_rate, 2)}</td>
                      <td className="ident">{proposal.route}</td>
                      <td className="ident">{proposal.created_by}</td>
                      <td className="ident">{proposal.approved_by ?? '—'}</td>
                      <td className="ident">{proposal.settled_by ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        );
      })}
    </div>
  );
}

function KernelLog() {
  const [verifying, setVerifying] = useState(false);
  const audit = useAudit({ limit: '200' });
  const chain = useChain(verifying);

  return (
    <div className="space-y-2">
      <Panel
        title="Chain integrity"
        subtitle="SHA-256, append-only, no update or delete path"
        actions={
          <Button variant="secondary" onClick={() => setVerifying(true)} disabled={chain.isFetching}>
            <ShieldCheck size={12} aria-hidden />
            {chain.isFetching ? 'Walking…' : 'Verify chain'}
          </Button>
        }
      >
        <div className="p-3">
          {!verifying ? (
            <p className="text-[12px] text-[var(--text-secondary)]">
              Verification recomputes every hash from sequence 1 and reports the first mismatch.
              Alter one row in the database and it names that exact sequence number.
            </p>
          ) : chain.isPending ? (
            <p className="text-[12px] text-[var(--text-tertiary)]">Walking the chain…</p>
          ) : chain.error ? (
            <ErrorState error={chain.error} onRetry={() => chain.refetch()} />
          ) : chain.data ? (
            <div className="flex items-start gap-2">
              {chain.data.intact ? (
                <CheckCircle2 size={16} className="mt-px text-[var(--ok-11)]" aria-hidden />
              ) : (
                <Link2Off size={16} className="mt-px text-[var(--err-11)]" aria-hidden />
              )}
              <div>
                <p
                  className="text-[13px] font-semibold"
                  style={{ color: chain.data.intact ? 'var(--ok-11)' : 'var(--err-11)' }}
                >
                  {chain.data.intact
                    ? `Intact across ${chain.data.checked} events`
                    : `Broken at sequence ${chain.data.broken_at}`}
                </p>
                {chain.data.reason ? (
                  <p className="mt-0.5 text-[11px] text-[var(--text-secondary)]">
                    {chain.data.reason}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </Panel>

      <Panel title="Kernel log" subtitle={`${audit.data?.length ?? 0} most recent events`}>
        {audit.isPending ? (
          <SkeletonRows rows={16} cols={6} dense />
        ) : (
          <table className="grid-table dense">
            <thead>
              <tr>
                <th scope="col" className="freeze-col">Seq</th>
                <th scope="col">Timestamp</th>
                <th scope="col">Actor</th>
                <th scope="col">Action</th>
                <th scope="col">Object</th>
                <th scope="col">Detail</th>
                <th scope="col">Hash</th>
              </tr>
            </thead>
            <tbody>
              {(audit.data ?? []).map((event) => (
                <tr key={event.seq}>
                  <td className="freeze-col ident">{event.seq}</td>
                  <td className="ident">{dateTime(event.ts)}</td>
                  <td className="ident">{event.actor_persona}</td>
                  <td className="ident">{event.action}</td>
                  <td className="ident">{event.object_id}</td>
                  <td title={event.detail}>{truncate(event.detail, 72)}</td>
                  <td className="ident text-[var(--text-tertiary)]" title={event.hash}>
                    {event.hash.slice(0, 10)}…
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
