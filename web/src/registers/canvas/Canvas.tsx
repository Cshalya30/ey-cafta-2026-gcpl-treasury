/**
 * CANVAS — one graph, eight lenses.
 *
 * The graph is GTC → three hubs → twelve entities. Layout is computed from the
 * data rather than hand-placed, so adding an entity cannot produce an overlap.
 * Keys 1 to 8 switch lens; Escape clears isolate mode; both live in the URL.
 */

import { useCallback, useEffect, useMemo } from 'react';
import { useQueryState } from 'nuqs';
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from '@xyflow/react';
import { Link } from 'react-router';
import { ArrowRight, Keyboard } from 'lucide-react';
import {
  useAppState,
  useCashLeak,
  useEntities,
  useExposures,
  useAccounts,
  useWorkflows,
} from '@/lib/hooks';
import { Badge, Panel, cn } from '@/components/primitives';
import { CoverageNote, ErrorState, SkeletonBlock } from '@/components/states';
import { UsdFigure } from '@/components/Figure';
import { LiveValue } from '@/components/LiveValue';
import { pct } from '@/lib/format';
import { Entity360 } from '@/features/entity360/Entity360';
import { LENSES, lensById } from './lenses';
import { nodeTypes } from './EntityNode';
import type { Entity as EntityType } from '@/lib/types';

// Layout constants. Entities are laid out as a grid beneath their own hub
// rather than as one long row: twelve nodes side by side forces fitView to
// shrink the cards past legibility at 1280 and 1440 px, which defeats the point.
const COLUMN = 236;
const ENTITY_ROW = 116;
const ROW_HUB = 150;
const ROW_ENTITY = 286;
const REGION_GAP = 60;

/** Columns to give a region's entity grid, so no region grows wider than three. */
function columnsFor(memberCount: number): number {
  if (memberCount <= 2) return Math.max(1, memberCount);
  if (memberCount <= 6) return 2;
  return 3;
}

export function Canvas() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

function CanvasInner() {
  const [lensId, setLensId] = useQueryState('lens', { defaultValue: 'cash' });
  const [entityId, setEntityId] = useQueryState('entity', { defaultValue: '' });
  const [isolate, setIsolate] = useQueryState('isolate', { defaultValue: '' });

  const state = useAppState();
  const entities = useEntities();
  const leak = useCashLeak();
  const exposures = useExposures();
  const accounts = useAccounts();
  const workflows = useWorkflows();

  const lens = lensById(lensId);

  // Keyboard 1 to 8 switches lens; Escape clears isolate mode.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const index = Number.parseInt(event.key, 10);
      if (index >= 1 && index <= 8) {
        const next = LENSES[index - 1];
        if (next) void setLensId(next.id);
      }
      if (event.key === 'Escape') void setIsolate('');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setLensId, setIsolate]);

  const context = useMemo(() => {
    const exposureByEntity = new Map<string, { notional: number; hedged: number }>();
    for (const exposure of exposures.data ?? []) {
      const current = exposureByEntity.get(exposure.entity_id) ?? { notional: 0, hedged: 0 };
      current.notional += exposure.notional_usd;
      current.hedged += exposure.hedged_usd;
      exposureByEntity.set(exposure.entity_id, current);
    }

    const banksByEntity = new Map<string, number>();
    const seen = new Map<string, Set<string>>();
    for (const account of accounts.data ?? []) {
      const set = seen.get(account.entity_id) ?? new Set<string>();
      set.add(account.bank_id);
      seen.set(account.entity_id, set);
    }
    for (const [id, set] of seen) banksByEntity.set(id, set.size);

    const leakByEntity = new Map<string, number>();
    for (const pair of leak.data?.pairs ?? []) {
      leakByEntity.set(
        pair.surplus_entity,
        (leakByEntity.get(pair.surplus_entity) ?? 0) + pair.annualised_leak_usd,
      );
    }

    // Breaches are a group-level control property; a workflow with a blocking
    // violation implicates every entity that executes it, so the group count is
    // shown on each node rather than invented per entity.
    const blocking = (workflows.data ?? []).reduce(
      (total, workflow) => total + workflow.blocking_count,
      0,
    );
    const breachesByEntity = new Map<string, number>();
    for (const entity of entities.data ?? []) {
      breachesByEntity.set(
        entity.id,
        entity.pool_status === 'restricted' || entity.onboard_status !== 'live'
          ? Math.min(blocking, 3)
          : 0,
      );
    }

    return {
      maxSurplusUsd: Math.max(
        1,
        ...(entities.data ?? []).map((e) =>
          Math.max(e.decomposition.deployable_surplus.usd, e.drawn.usd),
        ),
      ),
      maxExposureUsd: Math.max(1, ...[...exposureByEntity.values()].map((e) => e.notional)),
      leakByEntity,
      breachesByEntity,
      banksByEntity,
      exposureByEntity,
    };
  }, [entities.data, exposures.data, accounts.data, leak.data, workflows.data]);

  const { nodes, edges } = useMemo(() => {
    const list = entities.data ?? [];
    const regions = state.data?.regions ?? [];
    if (!list.length || !regions.length) return { nodes: [] as Node[], edges: [] as Edge[] };

    const isolated = isolate || null;
    const related = new Set<string>();
    if (isolated) {
      related.add(isolated);
      for (const pair of leak.data?.pairs ?? []) {
        if (pair.surplus_entity === isolated) related.add(pair.borrowing_entity);
        if (pair.borrowing_entity === isolated) related.add(pair.surplus_entity);
      }
      const self = list.find((e) => e.id === isolated);
      if (self?.parent_id) related.add(self.parent_id);
      for (const child of list) if (child.parent_id === isolated) related.add(child.id);
    }
    const dim = (id: string): boolean => Boolean(isolated) && !related.has(id);

    const byRegion = new Map<string, EntityType[]>();
    for (const entity of list) {
      byRegion.set(entity.region_id, [...(byRegion.get(entity.region_id) ?? []), entity]);
    }

    // Measure every region first, so the root can be centred over the whole set.
    const blocks = regions
      .map((region) => {
        const members = (byRegion.get(region.id) ?? [])
          .slice()
          .sort((a, b) => a.id.localeCompare(b.id));
        return { region, members, columns: columnsFor(members.length) };
      })
      .filter((block) => block.members.length > 0);

    const totalWidth =
      blocks.reduce((sum, block) => sum + block.columns * COLUMN, 0) +
      Math.max(0, blocks.length - 1) * REGION_GAP;

    const nodes: Node[] = [
      {
        id: 'GTC',
        type: 'group',
        position: { x: totalWidth / 2 - 118, y: 0 },
        data: {
          label: 'Group Treasury Centre',
          sub: `${list.length} entities · ${regions.length} hubs`,
          kind: 'root',
          dimmed: false,
        },
        draggable: false,
      },
    ];
    const edges: Edge[] = [];

    let cursor = 0;
    for (const { region, members, columns } of blocks) {
      const start = cursor;
      const span = columns * COLUMN;
      const hubX = start + span / 2 - 100;

      nodes.push({
        id: region.id,
        type: 'group',
        position: { x: hubX, y: ROW_HUB },
        data: {
          label: region.name,
          sub: `${region.hub_city} · ${region.coverage_hours}`,
          kind: 'hub',
          dimmed: Boolean(isolated),
        },
        draggable: false,
      });
      edges.push({
        id: `GTC-${region.id}`,
        source: 'GTC',
        target: region.id,
        style: { stroke: 'var(--border-interactive)', strokeWidth: 1 },
      });

      members.forEach((entity, index) => {
        const column = index % columns;
        const row = Math.floor(index / columns);
        nodes.push({
          id: entity.id,
          type: 'entity',
          position: { x: start + column * COLUMN, y: ROW_ENTITY + row * ENTITY_ROW },
          data: {
            entity,
            reading: lens.read(entity, context),
            lensLabel: lens.label,
            isolated: entity.id === isolated,
            dimmed: dim(entity.id),
          },
        });
        edges.push({
          id: `${region.id}-${entity.id}`,
          source: region.id,
          target: entity.id,
          style: {
            stroke: 'var(--border-subtle)',
            strokeWidth: 1,
            opacity: dim(entity.id) ? 0.2 : 1,
          },
        });
      });

      cursor += span + REGION_GAP;
    }

    // Lens 1 adds the Cash Leak edges: the one thing on this screen that is
    // not structure but loss, so it is the only thing that moves.
    if (lens.id === 'cash') {
      for (const pair of (leak.data?.pairs ?? []).slice(0, 6)) {
        const hidden = dim(pair.surplus_entity) && dim(pair.borrowing_entity);
        edges.push({
          id: `leak-${pair.surplus_entity}-${pair.borrowing_entity}`,
          source: pair.surplus_entity,
          target: pair.borrowing_entity,
          animated: false,
          className: 'leak-edge',
          label: `${pair.blocked_by.length ? '⚠ ' : ''}${compactUsd(pair.annualised_leak_usd)}/yr`,
          labelStyle: { fill: 'var(--err-11)', fontSize: 10, fontWeight: 600 },
          labelBgStyle: { fill: 'var(--surface-1)' },
          labelBgPadding: [4, 2] as [number, number],
          style: {
            stroke: 'var(--err-9)',
            strokeWidth: 1.6,
            opacity: hidden ? 0.12 : 1,
          },
        });
      }
    }

    if (lens.id === 'pooling') {
      for (const entity of list) {
        if (entity.pool_status !== 'eligible' || !entity.parent_id) continue;
        edges.push({
          id: `pool-${entity.id}`,
          source: entity.parent_id,
          target: entity.id,
          style: { stroke: 'var(--route-b)', strokeWidth: 1.4, opacity: dim(entity.id) ? 0.15 : 0.85 },
          label: `Route ${entity.route}`,
          labelStyle: { fill: 'var(--route-b)', fontSize: 9 },
          labelBgStyle: { fill: 'var(--surface-1)' },
        });
      }
    }

    return { nodes, edges };
  }, [entities.data, state.data, leak.data, lens, context, isolate]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type !== 'entity') return;
      void setEntityId(node.id);
    },
    [setEntityId],
  );

  const onNodeDoubleClick = useCallback(
    (_: unknown, node: Node) => {
      if (node.type !== 'entity') return;
      void setIsolate(isolate === node.id ? '' : node.id);
    },
    [isolate, setIsolate],
  );

  if (entities.error) return <ErrorState error={entities.error} onRetry={() => entities.refetch()} />;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <LensBar lensId={lens.id} onChange={(id) => void setLensId(id)} />

        <div className="relative min-h-0 flex-1">
          {entities.isPending ? (
            <div className="grid h-full place-items-center">
              <SkeletonBlock className="h-[320px] w-[min(900px,80%)] rounded-[6px]" />
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeDoubleClick}
              fitView
              fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
              minZoom={0.25}
              maxZoom={1.75}
              proOptions={{ hideAttribution: true }}
              nodesConnectable={false}
              nodesDraggable={false}
              aria-label={`Group structure, read through the ${lens.label} lens`}
            >
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#242424" />
              <Controls showInteractive={false} position="bottom-left" />
              {/* Small and translucent: a minimap that occludes a node card is
                  worse than no minimap on a dense graph. */}
              <MiniMap
                pannable
                zoomable
                position="bottom-right"
                style={{ width: 150, height: 96, opacity: 0.82 }}
                nodeColor={() => 'var(--surface-5)'}
                maskColor="rgba(22,22,22,0.6)"
              />
            </ReactFlow>
          )}

          {isolate ? (
            <div className="pointer-events-none absolute top-2 left-1/2 -translate-x-1/2">
              <Badge tone="info">
                Isolating {isolate} · press Escape to clear
              </Badge>
            </div>
          ) : null}
        </div>

        <LensFooter lens={lens} />
      </div>

      <aside className="flex w-[320px] shrink-0 flex-col gap-2 border-l border-[var(--border-subtle)] bg-[var(--surface-1)] p-2">
        <LeakPanel />
      </aside>

      <Entity360 entityId={entityId || null} onClose={() => void setEntityId('')} />
    </div>
  );
}

function LensBar({ lensId, onChange }: { lensId: string; onChange: (id: string) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Canvas lenses"
      className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-[var(--border-subtle)] bg-[var(--surface-2)] px-2 py-1.5"
    >
      {LENSES.map((lens) => {
        const active = lens.id === lensId;
        return (
          <button
            key={lens.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(lens.id)}
            title={`${lens.nodeEncodes}. Shortcut: ${lens.key}`}
            className={cn(
              'flex h-7 shrink-0 items-center gap-1.5 rounded-[3px] px-2.5 text-[12px] transition-colors duration-100',
              active
                ? 'bg-[var(--surface-4)] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--border-interactive)]'
                : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]',
            )}
          >
            <kbd
              className="ident rounded-[2px] bg-[var(--surface-1)] px-1 text-[10px] text-[var(--text-tertiary)]"
              aria-hidden
            >
              {lens.key}
            </kbd>
            {lens.label}
          </button>
        );
      })}
      <span className="ml-auto flex shrink-0 items-center gap-1 pr-1 text-[10px] text-[var(--text-tertiary)]">
        <Keyboard size={11} aria-hidden />
        click to open · double-click to isolate
      </span>
    </div>
  );
}

function LensFooter({ lens }: { lens: (typeof LENSES)[number] }) {
  return (
    <div className="flex shrink-0 items-center gap-4 border-t border-[var(--border-subtle)] bg-[var(--surface-2)] px-3 py-1.5 text-[11px] text-[var(--text-tertiary)]">
      <span>
        <strong className="font-medium text-[var(--text-secondary)]">Node:</strong>{' '}
        {lens.nodeEncodes}
      </span>
      <span>
        <strong className="font-medium text-[var(--text-secondary)]">Edge:</strong>{' '}
        {lens.edgeEncodes}
      </span>
      <span className="ml-auto">
        Colour is always paired with a glyph or a number; it never carries quantity alone.
      </span>
    </div>
  );
}

function LeakPanel() {
  const leak = useCashLeak();

  return (
    <Panel
      title="Cash leak"
      subtitle="computed on every load"
      actions={
        <Link
          to="/canvas/pooling"
          className="inline-flex h-6 items-center gap-1 rounded-[3px] bg-[var(--accent-9)] px-2 text-[11px] font-medium text-white no-underline hover:bg-[var(--accent-10)]"
        >
          Act on it
          <ArrowRight size={11} aria-hidden />
        </Link>
      }
      className="flex-1"
    >
      {leak.isPending ? (
        <div className="space-y-2 p-3">
          <SkeletonBlock className="h-10 w-3/4" />
          <SkeletonBlock className="h-16 w-full" />
        </div>
      ) : leak.error ? (
        <ErrorState error={leak.error} onRetry={() => leak.refetch()} />
      ) : leak.data ? (
        <div className="p-3">
          <p className="text-[10px] tracking-[0.08em] text-[var(--text-tertiary)] uppercase">
            Annualised, group-wide
          </p>
          <p className="tnum mt-0.5 text-[30px] leading-none font-bold text-[var(--err-11)]">
            <LiveValue value={leak.data.total_annualised_usd}>
              <UsdFigure usd={leak.data.total_annualised_usd} compact />
            </LiveValue>
          </p>
          <CoverageNote coverage={leak.data.coverage} className="mt-1.5" />

          <p className="mt-3 text-[11px] leading-relaxed text-[var(--text-secondary)]">
            Surplus cash sits in one entity at a deposit rate while another borrows externally at
            a credit spread. The group pays the full spread on the overlap, for as long as the
            overlap lasts. No single entity sees both halves.
          </p>

          <ul className="stagger mt-3 space-y-2">
            {leak.data.pairs.slice(0, 5).map((pair) => (
              <li
                key={`${pair.surplus_entity}-${pair.borrowing_entity}`}
                className="rounded-[3px] bg-[var(--surface-3)] p-2"
              >
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="ident truncate" translate="no">
                    {pair.surplus_entity}
                  </span>
                  <ArrowRight size={10} className="shrink-0 text-[var(--text-tertiary)]" aria-hidden />
                  <span className="ident truncate" translate="no">
                    {pair.borrowing_entity}
                  </span>
                  <span className="tnum ml-auto shrink-0 font-semibold text-[var(--err-11)]">
                    <UsdFigure usd={pair.annualised_leak_usd} compact />
                  </span>
                </div>
                <p className="tnum mt-1 text-[10px] text-[var(--text-tertiary)]">
                  {pct(pair.deposit_rate, 2)} deposit against {pct(pair.all_in_rate, 2)} borrowing ·
                  spread {pct(pair.spread, 2)} · Route {pair.route}
                </p>
                {pair.blocked_by.length ? (
                  <p className="mt-1 text-[10px] text-[var(--warn-11)]">{pair.blocked_by[0]}</p>
                ) : null}
              </li>
            ))}
          </ul>

          {leak.data.excluded.length ? (
            <div className="mt-3 rounded-[3px] bg-[var(--surface-3)] p-2">
              <p className="text-[10px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
                Excluded, declared not hidden
              </p>
              {leak.data.excluded.map((row) => (
                <p key={row.entity} className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  <span className="ident" translate="no">
                    {row.entity}
                  </span>{' '}
                  · <UsdFigure usd={row.trapped_usd} compact className="text-[var(--warn-11)]" />{' '}
                  trapped · {row.reason}
                </p>
              ))}
            </div>
          ) : null}

          <details className="mt-3">
            <summary className="cursor-pointer text-[11px] text-[var(--text-tertiary)]">
              Method
            </summary>
            <p className="mt-1 text-[10px] leading-relaxed text-[var(--text-tertiary)]">
              {leak.data.method}
            </p>
          </details>
        </div>
      ) : null}
    </Panel>
  );
}

/** Compact USD for an edge label, where the Figure component cannot be used. */
function compactUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}
