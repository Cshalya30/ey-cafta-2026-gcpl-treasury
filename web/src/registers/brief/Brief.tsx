/**
 * BRIEF — the CFO narrative, the KPI posters and the wave tracker.
 *
 * No number appears in the prose as a literal: every figure is interpolated
 * from the API, so the narrative cannot drift away from the data beneath it.
 */

import type { ReactNode } from 'react';
import { useQueryState } from 'nuqs';
import { Flag, Info } from 'lucide-react';
import {
  useAppState,
  useCashLeak,
  useEntities,
  useKpis,
  useOnboarding,
  useProgramme,
} from '@/lib/hooks';
import { Badge, Panel, cn } from '@/components/primitives';
import { CoverageNote, ErrorState, SkeletonRows } from '@/components/states';
import { Figure, UsdFigure } from '@/components/Figure';
import { count, date, pct, titleCase } from '@/lib/format';

const TABS = ['cfo', 'kpis', 'waves', 'day1'] as const;

/* Spelled out rather than title-cased: an initialism loses its capitals to a
   generic transform, and "Kpis" on a CFO's screen is a small but real tell. */
const TAB_LABEL: Record<(typeof TABS)[number], string> = {
  cfo: 'CFO narrative',
  kpis: 'KPIs',
  waves: 'Waves',
  day1: 'Day-1 kit',
};

export function Brief() {
  const [tab, setTab] = useQueryState('tab', { defaultValue: 'cfo' });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav
        role="tablist"
        aria-label="Brief sections"
        className="flex shrink-0 gap-1 border-b border-[var(--border-subtle)] bg-[var(--surface-2)] px-2 py-1.5"
      >
        {TABS.map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            onClick={() => void setTab(name)}
            className={cn(
              'h-7 rounded-[3px] px-2.5 text-[12px] transition-colors duration-100',
              tab === name
                ? 'bg-[var(--surface-4)] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--border-interactive)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
            )}
          >
            {TAB_LABEL[name]}
          </button>
        ))}
      </nav>

      <div
        role="tabpanel"
        tabIndex={0}
        aria-label={`Brief: ${tab}`}
        className="min-h-0 flex-1 overflow-auto p-3"
      >
        {tab === 'cfo' ? (
          <Narrative />
        ) : tab === 'kpis' ? (
          <KpiPosters />
        ) : tab === 'waves' ? (
          <WaveTracker />
        ) : (
          <DayOneKit />
        )}
      </div>
    </div>
  );
}

function Narrative() {
  const state = useAppState();
  const leak = useCashLeak();
  const entities = useEntities();

  if (state.isPending || leak.isPending || entities.isPending) {
    return <SkeletonRows rows={10} cols={3} />;
  }
  if (leak.error) return <ErrorState error={leak.error} onRetry={() => leak.refetch()} />;

  const summary = state.data?.summary;
  const list = entities.data ?? [];
  if (!summary || !leak.data) return null;

  const routeD = list.filter((entity) => entity.route === 'D');
  const trapped = leak.data.excluded.reduce((sum, row) => sum + row.trapped_usd, 0);
  const degraded = summary.coverage.accounts_total - summary.coverage.accounts_current;
  const topPair = leak.data.pairs[0];

  return (
    <div className="mx-auto max-w-[80ch] space-y-4">
      <header>
        <p className="text-[11px] tracking-[0.08em] text-[var(--text-tertiary)] uppercase">
          Treasury Committee · as at {date(summary.as_of)}
        </p>
        <h1 className="mt-1 text-[26px] leading-tight font-semibold">
          The group pays a spread it does not have to pay.
        </h1>
      </header>

      <div
        className="rounded-[6px] p-4"
        style={{ background: 'var(--err-3)', boxShadow: 'inset 0 0 0 1px var(--err-9)' }}
      >
        <p className="text-[11px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
          Annualised cash leak
        </p>
        <p className="tnum mt-1 text-[38px] leading-none font-bold text-[var(--err-11)]">
          <UsdFigure usd={leak.data.total_annualised_usd} />
        </p>
        <CoverageNote coverage={leak.data.coverage} className="mt-2" />
      </div>

      <section className="space-y-3 text-[14px] leading-relaxed text-[var(--text-secondary)]">
        <p>
          Across {count(summary.entity_count)} entities the group holds{' '}
          <Strong><Figure value={summary.total_cash} /></Strong> in cash. Of that,{' '}
          <Strong><Figure value={summary.restricted} /></Strong> is restricted and{' '}
          <Strong><Figure value={summary.operating_buffer} /></Strong> is local operating buffer
          that is never sweepable. What remains deployable is{' '}
          <Strong><Figure value={summary.deployable_surplus} /></Strong>.
        </p>

        <p>
          At the same time the group carries{' '}
          <Strong><Figure value={summary.drawn} /></Strong> of drawn external debt against{' '}
          <Strong><Figure value={summary.committed} /></Strong> committed. Those two facts sit in
          different legal entities and, today, in different spreadsheets.
          {topPair ? (
            <>
              {' '}The largest single overlap is{' '}
              <Strong>{topPair.surplus_entity}</Strong> earning{' '}
              <Strong>{pct(topPair.deposit_rate, 2)}</Strong> on deposit while{' '}
              <Strong>{topPair.borrowing_entity}</Strong> borrows at{' '}
              <Strong>{pct(topPair.all_in_rate, 2)}</Strong> — a spread of{' '}
              <Strong>{pct(topPair.spread, 2)}</Strong> on{' '}
              <Strong><UsdFigure usd={topPair.overlap_usd} /></Strong>, or{' '}
              <Strong><UsdFigure usd={topPair.annualised_leak_usd} /></Strong> a year.
            </>
          ) : null}
        </p>

        <p>
          Not all of it is recoverable, and the brief says so.{' '}
          {routeD.length ? (
            <>
              <Strong>{count(routeD.length)}</Strong>{' '}
              {routeD.length === 1 ? 'entity sits' : 'entities sit'} on Route D, where exchange
              control keeps <Strong><UsdFigure usd={trapped} /></Strong> local. That cash is
              declared as trapped rather than counted toward a number nobody can realise.
            </>
          ) : (
            'No entity is currently exchange-control restricted.'
          )}
        </p>

        <p>
          Visibility is the constraint before structure is.{' '}
          <Strong>{summary.coverage.statement}</Strong>.
          {degraded > 0 ? (
            <>
              {' '}The remaining <Strong>{count(degraded)}</Strong> are stale or offline, and they
              are shown with their age rather than hidden — hiding them would make the group look
              more current than it is.
            </>
          ) : null}
        </p>

        <p>
          The recommendation is unchanged: stand up this control layer now, measure the real
          overlap for ninety days, and take the TMS decision at month four on evidence rather than
          on a vendor's assertion. This layer is explicitly temporary. It retires into whichever
          system the Committee selects.
        </p>
      </section>

      <aside
        className="flex items-start gap-2 rounded-[4px] p-3"
        style={{ background: 'var(--surface-3)' }}
      >
        <Info size={14} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" aria-hidden />
        <p className="text-[11px] leading-relaxed text-[var(--text-tertiary)]">
          Every figure in this narrative is interpolated from the API at render time. There is no
          number written into the prose. Method: {leak.data.method}
        </p>
      </aside>
    </div>
  );
}

function Strong({ children }: { children: ReactNode }) {
  return <strong className="tnum font-semibold text-[var(--text-primary)]">{children}</strong>;
}

function KpiPosters() {
  const kpis = useKpis();
  if (kpis.isPending) return <SkeletonRows rows={9} cols={4} />;
  if (kpis.error) return <ErrorState error={kpis.error} onRetry={() => kpis.refetch()} />;

  return (
    <div className="grid grid-cols-3 gap-2">
      {(kpis.data ?? []).map((kpi) => (
        <Panel key={kpi.code}>
          <div className="p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[11px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
                {kpi.label}
              </p>
              <Badge tone={kpi.on_target ? 'ok' : 'warn'}>
                {kpi.on_target ? 'on target' : 'off target'}
              </Badge>
            </div>

            <p
              className="tnum mt-2 text-[30px] leading-none font-bold"
              style={{ color: kpi.on_target ? 'var(--ok-11)' : 'var(--warn-11)' }}
            >
              {kpi.unit === 'pct' ? (
                pct(kpi.value)
              ) : kpi.unit === 'usd' ? (
                <UsdFigure usd={kpi.value} compact />
              ) : (
                count(Math.round(kpi.value))
              )}
            </p>

            <p className="tnum mt-1 text-[11px] text-[var(--text-tertiary)]">
              Target{' '}
              {kpi.unit === 'pct'
                ? pct(kpi.target)
                : kpi.unit === 'usd'
                  ? new Intl.NumberFormat('en-US', {
                      style: 'currency',
                      currency: 'USD',
                      notation: 'compact',
                      maximumFractionDigits: 1,
                    }).format(kpi.target)
                  : count(kpi.target)}{' '}
              · {kpi.direction === 'higher_is_better' ? 'higher is better' : 'lower is better'}
            </p>

            {/* Evidence footnote: as-of, source and stale count on every tile. */}
            <footer className="mt-3 border-t border-[var(--border-subtle)] pt-2">
              <p className="text-[10px] leading-relaxed text-[var(--text-tertiary)]">
                As at {date(kpi.as_of)} · {kpi.source}
                {kpi.stale_count > 0 ? ` · ${count(kpi.stale_count)} stale feeds` : ''}
              </p>
            </footer>
          </div>
        </Panel>
      ))}
    </div>
  );
}

function WaveTracker() {
  const programme = useProgramme();
  if (programme.isPending) return <SkeletonRows rows={6} cols={4} />;
  if (programme.error) return <ErrorState error={programme.error} onRetry={() => programme.refetch()} />;
  const data = programme.data;
  if (!data) return null;

  const months = data.horizon_months;

  return (
    <div className="space-y-2">
      <Panel title="Programme waves" subtitle="waves overlap; they are not a staircase">
        <div className="p-4">
          {/* Month ruler */}
          <div className="relative mb-2 ml-[180px] h-4">
            {Array.from({ length: Math.floor(months / 3) + 1 }, (_, index) => index * 3).map(
              (month) => (
                <span
                  key={month}
                  className="tnum absolute text-[10px] text-[var(--text-tertiary)]"
                  style={{
                    left: `${(month / months) * 100}%`,
                    // The final tick sits at the ruler's right edge; left-anchored
                    // like every other tick, its own label text ran past the
                    // container and was clipped by the viewport.
                    transform: month === months ? 'translateX(-100%)' : undefined,
                  }}
                >
                  M{month}
                </span>
              ),
            )}
          </div>

          <ul className="space-y-1.5">
            {data.waves.map((wave) => (
              <li key={wave.id} className="flex items-center gap-2">
                <span className="w-[172px] shrink-0 truncate text-[11px]">
                  <span className="ident mr-1.5 text-[var(--text-tertiary)]">{wave.id}</span>
                  {wave.name}
                </span>
                <div className="relative h-6 flex-1 rounded-[2px] bg-[var(--surface-3)]">
                  <div
                    className="absolute top-0 h-full rounded-[2px]"
                    title={`${wave.name}: month ${wave.start_month} to ${wave.end_month}. ${wave.description}`}
                    style={{
                      left: `${(wave.start_month / months) * 100}%`,
                      width: `${((wave.end_month - wave.start_month) / months) * 100}%`,
                      background: 'var(--accent-9)',
                      opacity: 0.85,
                    }}
                  />
                  {data.gates.map((gate) => (
                    <span
                      key={gate.id}
                      className="absolute top-0 h-full w-px"
                      style={{
                        left: `${(gate.month / months) * 100}%`,
                        background:
                          gate.status === 'passed' ? 'var(--ok-9)' : 'var(--border-strong)',
                      }}
                      aria-hidden
                    />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      <Panel title="Gates" subtitle={`${data.gates.length} decision points`}>
        <ul className="divide-y divide-[var(--border-subtle)]">
          {data.gates.map((gate) => (
            <li key={gate.id} className="flex items-start gap-3 px-3 py-2.5">
              <Flag
                size={14}
                className="mt-0.5 shrink-0"
                style={{
                  color:
                    gate.status === 'passed'
                      ? 'var(--ok-11)'
                      : gate.status === 'failed'
                        ? 'var(--err-11)'
                        : 'var(--text-tertiary)',
                }}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="ident text-[11px] font-semibold">{gate.id}</span>
                  <span className="tnum text-[11px] text-[var(--text-tertiary)]">
                    Month {gate.month}
                  </span>
                  <Badge
                    tone={gate.status === 'passed' ? 'ok' : gate.status === 'failed' ? 'err' : 'neutral'}
                  >
                    {titleCase(gate.status)}
                  </Badge>
                </div>
                <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{gate.criterion}</p>
              </div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function DayOneKit() {
  const entities = useEntities();
  const [entityId, setEntityId] = useQueryState('entity', { defaultValue: '' });
  const list = entities.data ?? [];
  const selected = entityId || list.find((e) => e.onboard_status !== 'live')?.id || list[0]?.id || '';
  const onboarding = useOnboarding(selected || null);

  return (
    <div className="space-y-2">
      <Panel title="Day-1 kit" subtitle="the seven items that take an acquired entity to reporting">
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2">
          <label htmlFor="kit-entity" className="text-[11px] text-[var(--text-secondary)]">
            Entity
          </label>
          <select
            id="kit-entity"
            value={selected}
            onChange={(event) => void setEntityId(event.target.value)}
            className="h-6 rounded-[3px] px-1.5 text-[11px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
          >
            {list.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.short_name} · {titleCase(entity.onboard_status)}
              </option>
            ))}
          </select>
        </div>

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
    </div>
  );
}
