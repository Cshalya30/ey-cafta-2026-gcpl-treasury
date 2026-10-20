/**
 * Pooling Workbench.
 *
 * Moving a slider re-evaluates all nine checks on the server and recomputes the
 * economics from the caller's own parameters. Nothing here reads a stored
 * constant: change the borrowing rate in the database, reload, and the numbers
 * move.
 */

import { useEffect, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';
import { AlertTriangle, CheckCircle2, Loader2, ShieldAlert, Send } from 'lucide-react';
import {
  useAppState,
  useCashLeak,
  useCreateProposal,
  useEntities,
  useEvaluate,
} from '@/lib/hooks';
import { Badge, Button, Field, Panel, RouteBadge, Stat } from '@/components/primitives';
import { ErrorState, SkeletonRows } from '@/components/states';
import { UsdFigure } from '@/components/Figure';
import { LiveValue } from '@/components/LiveValue';
import { bps, pct } from '@/lib/format';
import type { Check, Evaluation } from '@/lib/types';

const DEBOUNCE_MS = 120;

export function PoolingWorkbench() {
  const entities = useEntities();
  const leak = useCashLeak();
  const state = useAppState();

  const [source, setSource] = useQueryState('source', { defaultValue: '' });
  const [target, setTarget] = useQueryState('target', { defaultValue: '' });
  const [amount, setAmount] = useState(0);
  const [tenor, setTenor] = useState(180);
  const [rate, setRate] = useState(0.08);
  const [justification, setJustification] = useState('');
  const [touched, setTouched] = useState(false);

  const evaluate = useEvaluate();
  const create = useCreateProposal();
  const timer = useRef<number | null>(null);

  // Seed from the largest leak pair, so the workbench opens on the problem the
  // Canvas just showed rather than on an empty form.
  useEffect(() => {
    const top = leak.data?.pairs[0];
    if (!top || source || target) return;
    void setSource(top.surplus_entity);
    void setTarget(top.borrowing_entity);
    setAmount(Math.round(top.overlap_usd));
    setRate(Math.max(top.deposit_rate + 0.02, 0.05));
  }, [leak.data, source, target, setSource, setTarget]);

  const list = entities.data ?? [];
  const sourceEntity = list.find((e) => e.id === source);
  const targetEntity = list.find((e) => e.id === target);
  const maxAmount = Math.max(
    1,
    Math.round(sourceEntity?.decomposition.deployable_surplus.usd ?? 1_000_000),
  );

  useEffect(() => {
    if (!source || !target || amount <= 0) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      evaluate.mutate({
        source_entity_id: source,
        target_entity_id: target,
        amount_usd: amount,
        tenor_days: tenor,
        interest_rate: rate,
      });
    }, DEBOUNCE_MS);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
    // evaluate.mutate is stable for the lifetime of the mutation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, target, amount, tenor, rate]);

  const result = evaluate.data as Evaluation | undefined;
  const blocking = result?.blocking_count ?? 0;
  const canInitiate = state.data?.persona.can_initiate ?? false;
  const justificationError =
    touched && justification.trim().length < 4
      ? 'A justification of at least four characters is recorded against this proposal.'
      : null;

  const submitDisabled =
    !canInitiate || !result || blocking > 0 || justification.trim().length < 4 || create.isPending;

  if (entities.error) return <ErrorState error={entities.error} onRetry={() => entities.refetch()} />;

  return (
    <div className="grid h-full min-h-0 grid-cols-[360px_1fr_380px] gap-2 overflow-hidden p-2">
      {/* ── parameters ─────────────────────────────────────────── */}
      <Panel title="Proposal" subtitle="all figures in USD">
        {entities.isPending ? (
          <SkeletonRows rows={6} cols={2} />
        ) : (
          <div className="space-y-3 p-3">
            <Field label="Source entity, holding surplus" htmlFor="source">
              <select
                id="source"
                value={source}
                onChange={(event) => void setSource(event.target.value)}
                className="h-8 rounded-[3px] px-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
              >
                <option value="">Select…</option>
                {list
                  .filter((entity) => entity.decomposition.deployable_surplus.usd > 0)
                  .map((entity) => (
                    <option key={entity.id} value={entity.id}>
                      {entity.short_name} ({entity.id})
                    </option>
                  ))}
              </select>
            </Field>

            <Field label="Target entity, carrying drawn debt" htmlFor="target">
              <select
                id="target"
                value={target}
                onChange={(event) => void setTarget(event.target.value)}
                className="h-8 rounded-[3px] px-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
              >
                <option value="">Select…</option>
                {list
                  .filter((entity) => entity.drawn.usd > 0)
                  .map((entity) => (
                    <option key={entity.id} value={entity.id}>
                      {entity.short_name} ({entity.id})
                    </option>
                  ))}
              </select>
            </Field>

            <Field
              label="Amount"
              htmlFor="amount"
              hint={`Capped at the source's deployable surplus of ${formatUsd(maxAmount)}.`}
            >
              <div className="flex items-center gap-2">
                <input
                  id="amount"
                  type="range"
                  min={0}
                  max={maxAmount}
                  step={Math.max(1, Math.round(maxAmount / 200))}
                  value={Math.min(amount, maxAmount)}
                  onChange={(event) => setAmount(Number(event.target.value))}
                  className="flex-1 accent-[var(--accent-9)]"
                />
                <output
                  htmlFor="amount"
                  className="tnum w-[92px] shrink-0 text-right text-[12px] font-semibold"
                >
                  <UsdFigure usd={amount} compact />
                </output>
              </div>
            </Field>

            <Field label="Tenor" htmlFor="tenor" hint="Days until repayment.">
              <div className="flex items-center gap-2">
                <input
                  id="tenor"
                  type="range"
                  min={1}
                  max={730}
                  step={1}
                  value={tenor}
                  onChange={(event) => setTenor(Number(event.target.value))}
                  className="flex-1 accent-[var(--accent-9)]"
                />
                <output className="tnum w-[92px] shrink-0 text-right text-[12px] font-semibold">
                  {tenor} days
                </output>
              </div>
            </Field>

            <Field
              label="Intercompany rate"
              htmlFor="rate"
              hint={
                result
                  ? `Safe-harbour floor: ${pct(result.economics.safe_harbour_floor, 2)}.`
                  : 'The floor is computed from the source currency and the loan size.'
              }
            >
              <div className="flex items-center gap-2">
                <input
                  id="rate"
                  type="range"
                  min={0}
                  max={0.3}
                  step={0.0005}
                  value={rate}
                  onChange={(event) => setRate(Number(event.target.value))}
                  className="flex-1 accent-[var(--accent-9)]"
                />
                <output className="tnum w-[92px] shrink-0 text-right text-[12px] font-semibold">
                  {pct(rate, 2)}
                </output>
              </div>
            </Field>

            {sourceEntity && targetEntity ? (
              <div className="flex items-center gap-2 rounded-[3px] bg-[var(--surface-3)] p-2 text-[11px]">
                <RouteBadge route={sourceEntity.route} />
                <span className="text-[var(--text-tertiary)]">→</span>
                <RouteBadge route={targetEntity.route} />
                <span className="ml-auto text-[var(--text-tertiary)]">
                  {sourceEntity.country_iso2} to {targetEntity.country_iso2}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </Panel>

      {/* ── nine checks ────────────────────────────────────────── */}
      <Panel
        title="Nine-constraint verification"
        subtitle={
          evaluate.isPending
            ? 'evaluating…'
            : result
              ? `${result.checks.length - blocking - result.warning_count} clear · ${result.warning_count} warning · ${blocking} blocking`
              : 'select a source and a target'
        }
        actions={
          evaluate.isPending ? (
            <Loader2 size={13} className="animate-spin text-[var(--text-tertiary)]" aria-hidden />
          ) : null
        }
      >
        {evaluate.error ? (
          <ErrorState error={evaluate.error} />
        ) : !result ? (
          <div className="p-5 text-[12px] text-[var(--text-tertiary)]">
            Choose a source entity holding deployable surplus and a target entity carrying drawn
            debt. Every check below will show the arithmetic it used.
          </div>
        ) : (
          <ol className="divide-y divide-[var(--border-subtle)]">
            {result.checks.map((check) => (
              <CheckRow key={check.check_no} check={check} />
            ))}
          </ol>
        )}
      </Panel>

      {/* ── economics and submit ───────────────────────────────── */}
      <div className="flex min-h-0 flex-col gap-2">
        <Panel title="Indicative economics" subtitle="recomputed from your parameters">
          {result ? (
            <div className="space-y-3 p-3">
              <div className="grid grid-cols-2 gap-3">
                <Stat
                  label="Source deposit rate"
                  value={pct(result.economics.source_deposit_rate, 2)}
                />
                <Stat
                  label="Target all-in rate"
                  value={pct(result.economics.target_all_in_rate, 2)}
                  tone="err"
                />
                <Stat
                  label="Spread"
                  value={
                    <LiveValue value={result.economics.spread}>
                      {bps(result.economics.spread)}
                    </LiveValue>
                  }
                />
                <Stat
                  label="Safe-harbour floor"
                  value={pct(result.economics.safe_harbour_floor, 2)}
                  tone={rate >= result.economics.safe_harbour_floor ? 'ok' : 'err'}
                />
              </div>
              <div className="rounded-[3px] bg-[var(--surface-3)] p-2">
                <Stat
                  label="Annual saving to the group"
                  value={
                    <LiveValue value={result.economics.annual_saving_usd}>
                      <UsdFigure usd={result.economics.annual_saving_usd} />
                    </LiveValue>
                  }
                  tone="ok"
                  sub={`Over ${tenor} days: ${formatUsd(result.economics.period_saving_usd)}`}
                />
              </div>
              <p className="text-[10px] leading-relaxed text-[var(--text-tertiary)]">
                {result.economics.workings}
              </p>
              <p className="text-[10px] leading-relaxed text-[var(--text-tertiary)]">
                {result.economics.safe_harbour_basis}. {result.economics.safe_harbour_citation}
              </p>
            </div>
          ) : (
            <div className="p-5 text-[12px] text-[var(--text-tertiary)]">
              Economics appear once both entities are chosen.
            </div>
          )}
        </Panel>

        <Panel title="Submit for approval" className="shrink-0">
          <form
            className="space-y-2 p-3"
            onSubmit={(event) => {
              event.preventDefault();
              setTouched(true);
              if (submitDisabled || !sourceEntity) return;
              create.mutate({
                kind: 'intercompany_loan',
                source_entity_id: source,
                target_entity_id: target,
                amount_usd: amount,
                tenor_days: tenor,
                interest_rate: rate,
                rate_basis: result?.economics.safe_harbour_basis ?? 'computed floor',
                justification: justification.trim(),
              });
            }}
          >
            <Field
              label="Justification"
              htmlFor="justification"
              hint="LR7: recorded against the proposal and written to the audit chain."
              error={justificationError}
            >
              <textarea
                id="justification"
                value={justification}
                onChange={(event) => setJustification(event.target.value)}
                onBlur={() => setTouched(true)}
                required
                minLength={4}
                maxLength={500}
                rows={2}
                aria-invalid={Boolean(justificationError)}
                aria-describedby={justificationError ? 'justification-error' : 'justification-hint'}
                className="resize-none rounded-[3px] bg-[var(--surface-1)] p-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
                placeholder="Why this movement, and why now."
              />
            </Field>

            {!canInitiate ? (
              <p
                data-testid="no-initiate-notice"
                className="rounded-[3px] p-2 text-[11px]"
                style={{ background: 'var(--warn-3)', color: 'var(--text-primary)' }}
              >
                Your persona holds no initiate capability. The control is disabled here, and the
                API rejects the call regardless: hiding the button is not the control.
              </p>
            ) : null}

            {blocking > 0 ? (
              <p className="flex items-start gap-1.5 text-[11px] text-[var(--err-11)]">
                <ShieldAlert size={12} className="mt-0.5 shrink-0" aria-hidden />
                {blocking} blocking check(s) must clear before this can be submitted.
              </p>
            ) : null}

            {create.error ? <ErrorState error={create.error} /> : null}
            {create.data ? (
              <p className="flex items-center gap-1.5 text-[11px] text-[var(--ok-11)]">
                <CheckCircle2 size={12} aria-hidden />
                Created <span className="ident">{create.data.id}</span>, now{' '}
                {create.data.status.replace('_', ' ')}. Approval sits with a different holder.
              </p>
            ) : null}

            <Button type="submit" variant="primary" disabled={submitDisabled} className="w-full">
              <Send size={12} aria-hidden />
              {create.isPending ? 'Submitting…' : 'Submit for approval'}
            </Button>
          </form>
        </Panel>
      </div>
    </div>
  );
}

function CheckRow({ check }: { check: Check }) {
  const tone = check.result === 'OKAY' ? 'ok' : check.result === 'WARN' ? 'warn' : 'err';
  const Icon =
    check.result === 'OKAY' ? CheckCircle2 : check.result === 'WARN' ? AlertTriangle : ShieldAlert;

  return (
    <li
      className="flex gap-2.5 px-3 py-2"
      style={{
        background:
          check.result === 'ERR'
            ? 'var(--err-3)'
            : check.result === 'WARN'
              ? 'var(--warn-3)'
              : 'transparent',
      }}
    >
      <span className="tnum w-4 shrink-0 pt-px text-[11px] text-[var(--text-tertiary)]">
        {check.check_no}
      </span>
      <Icon
        size={13}
        className="mt-px shrink-0"
        style={{
          color:
            tone === 'ok' ? 'var(--ok-11)' : tone === 'warn' ? 'var(--warn-11)' : 'var(--err-11)',
        }}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="ident text-[11px] font-semibold">{check.code}</span>
          <Badge tone={tone}>{check.result}</Badge>
        </div>
        {/* A check that says only "passed" is useless; it must show its arithmetic. */}
        <p className="tnum mt-0.5 text-[11px] leading-relaxed text-[var(--text-secondary)]">
          {check.detail}
        </p>
      </div>
    </li>
  );
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
}
