/**
 * Workflow Studio.
 *
 * Seven swimlanes, fifteen pre-loaded workflows, LR1 to LR16 on every change.
 * Dragging a node into a different lane re-runs the linter on the server and
 * surfaces whatever it finds, with the offending node highlighted.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  ViewportPortal,
  MarkerType,
  type Edge,
  type Node,
} from '@xyflow/react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { PlayCircle, ScanLine, ShieldAlert, ShieldCheck } from 'lucide-react';
import {
  useAppState,
  useLintWorkflow,
  useMoveNode,
  useSimulate,
  useSodRules,
  useWorkflow,
  useWorkflows,
} from '@/lib/hooks';
import { Badge, Button, Panel, cn } from '@/components/primitives';
import { ErrorState, SkeletonRows } from '@/components/states';
import type { Violation } from '@/lib/types';

const LANES = ['local', 'front', 'middle', 'tax_legal', 'regional', 'group', 'back'] as const;
const LANE_HEIGHT = 140;
const LANE_LABEL: Record<string, string> = {
  local: 'Local entity',
  front: 'Front Office',
  middle: 'Middle Office',
  tax_legal: 'Tax and Legal',
  regional: 'Regional',
  group: 'Group',
  back: 'Back Office',
};

export function WorkflowStudio() {
  return (
    <ReactFlowProvider>
      <StudioInner />
    </ReactFlowProvider>
  );
}

function StudioInner() {
  const { workflowId = 'W1' } = useParams();
  const workflows = useWorkflows();
  const workflow = useWorkflow(workflowId);
  const rules = useSodRules();
  const state = useAppState();
  const lint = useLintWorkflow();
  const move = useMoveNode();
  const simulate = useSimulate();
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    // simulate.reset is stable for the lifetime of the mutation.
    simulate.reset();
    setSelected(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  const detail = workflow.data;
  const isRisk = state.data?.persona.id === 'P6';

  const violationsByNode = useMemo(() => {
    const map = new Map<string, Violation[]>();
    for (const violation of detail?.violations ?? []) {
      if (!violation.node_id) continue;
      map.set(violation.node_id, [...(map.get(violation.node_id) ?? []), violation]);
    }
    return map;
  }, [detail]);

  const graphWidth = useMemo(
    () => Math.max(900, ...(detail?.nodes ?? []).map((node) => node.pos_x + 200)),
    [detail],
  );

  const { nodes, edges } = useMemo(() => {
    if (!detail) return { nodes: [] as Node[], edges: [] as Edge[] };

    const nodes: Node[] = detail.nodes.map((node) => ({
      id: node.id,
      type: 'step',
      position: { x: node.pos_x, y: LANES.indexOf(node.lane as (typeof LANES)[number]) * LANE_HEIGHT },
      data: {
        label: node.label,
        lane: node.lane,
        kind: node.node_kind,
        persona: node.required_persona,
        violations: violationsByNode.get(node.id) ?? [],
        isBlocked: (violationsByNode.get(node.id) ?? []).some((v) => v.severity === 'block'),
      },
      draggable: isRisk,
    }));

    const edges: Edge[] = detail.edges.map((edge) => ({
      id: edge.id,
      source: edge.from_node,
      target: edge.to_node,
      label: edge.condition_label ?? undefined,
      labelStyle: { fill: 'var(--text-tertiary)', fontSize: 9 },
      labelBgStyle: { fill: 'var(--surface-1)' },
      labelBgPadding: [3, 2] as [number, number],
      style: { stroke: 'var(--border-interactive)', strokeWidth: 1.2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--border-strong)' },
    }));

    return { nodes, edges };
  }, [detail, violationsByNode, isRisk]);

  const onNodeDragStop = useCallback(
    (_: unknown, node: Node) => {
      if (!isRisk || !detail) return;
      const laneIndex = Math.max(
        0,
        Math.min(LANES.length - 1, Math.round(node.position.y / LANE_HEIGHT)),
      );
      const lane = LANES[laneIndex]!;
      move.mutate({
        workflowId: detail.id,
        node_id: node.id,
        lane,
        pos_x: node.position.x,
        pos_y: laneIndex * LANE_HEIGHT,
      });
    },
    [isRisk, detail, move],
  );

  if (workflow.error) return <ErrorState error={workflow.error} onRetry={() => workflow.refetch()} />;

  return (
    <div className="grid h-full min-h-0 grid-cols-[240px_1fr_340px] gap-2 overflow-hidden p-2">
      <Panel title="Workflows" subtitle={`${workflows.data?.length ?? 0} loaded`}>
        {workflows.isPending ? (
          <SkeletonRows rows={10} cols={2} dense />
        ) : (
          <ul>
            {(workflows.data ?? []).map((item) => (
              <li key={item.id}>
                <Link
                  to={`/canvas/workflow/${item.id}`}
                  className={cn(
                    'flex items-center gap-2 px-2.5 py-1.5 text-[11px] no-underline',
                    item.id === workflowId
                      ? 'bg-[var(--surface-4)] text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
                  )}
                >
                  <span className="ident w-7 shrink-0 text-[var(--text-tertiary)]">{item.id}</span>
                  <span className="min-w-0 flex-1 truncate">{item.name}</span>
                  {item.blocking_count ? (
                    <Badge tone="err">{item.blocking_count}</Badge>
                  ) : item.violation_count ? (
                    <Badge tone="warn">{item.violation_count}</Badge>
                  ) : (
                    <ShieldCheck size={11} className="shrink-0 text-[var(--ok-11)]" aria-hidden />
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title={detail ? `${detail.id} · ${detail.name}` : 'Loading…'}
        subtitle={detail?.description}
        actions={
          <>
            <Button
              variant="secondary"
              disabled={!isRisk || lint.isPending}
              title={
                isRisk
                  ? 'Run LR1 to LR16 and persist the result'
                  : 'Only the Risk and Control Analyst may run the linter'
              }
              onClick={() => detail && lint.mutate(detail.id)}
            >
              <ScanLine size={12} aria-hidden />
              {lint.isPending ? 'Linting…' : 'Lint'}
            </Button>
            <Button
              variant="secondary"
              disabled={simulate.isPending}
              onClick={() => detail && simulate.mutate(detail.id)}
            >
              <PlayCircle size={12} aria-hidden />
              Simulate
            </Button>
          </>
        }
      >
        {workflow.isPending ? (
          <SkeletonRows rows={8} cols={4} />
        ) : (
          <div className="relative h-full min-h-[420px]">
            <ReactFlow
              colorMode="dark"
              nodes={nodes}
              edges={edges}
              nodeTypes={stepNodeTypes}
              onNodeDragStop={onNodeDragStop}
              onNodeClick={(_, node) => setSelected(node.id)}
              fitView
              fitViewOptions={{ padding: 0.1, maxZoom: 1 }}
              minZoom={0.3}
              maxZoom={1.6}
              nodesConnectable={false}
              proOptions={{ hideAttribution: true }}
              aria-label={`Workflow ${detail?.id} swimlane diagram`}
            >
              {/* Inside the flow, so a band stays locked to the nodes it
                  contains at every zoom level. */}
              <LaneBackdrop width={graphWidth} />
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#242424" />
              <Controls showInteractive={false} position="bottom-left" />
            </ReactFlow>
            {!isRisk ? (
              <p className="pointer-events-none absolute top-2 right-2 rounded-[3px] bg-[var(--surface-3)] px-2 py-1 text-[10px] text-[var(--text-tertiary)]">
                Switch to the Risk and Control Analyst to edit lanes.
              </p>
            ) : null}
          </div>
        )}
      </Panel>

      <div className="flex min-h-0 flex-col gap-2">
        <Panel
          title="Violations"
          subtitle={
            detail
              ? `${detail.blocking_count} blocking · ${detail.violation_count - detail.blocking_count} warning`
              : undefined
          }
          className="flex-1"
        >
          {detail?.violations.length ? (
            <ul className="divide-y divide-[var(--border-subtle)]">
              {detail.violations.map((violation) => (
                <li
                  key={`${violation.rule_id}-${violation.node_id ?? 'wf'}`}
                  className={cn(
                    'px-3 py-2',
                    selected && violation.node_id === selected && 'bg-[var(--surface-3)]',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <ShieldAlert
                      size={12}
                      style={{
                        color:
                          violation.severity === 'block' ? 'var(--err-11)' : 'var(--warn-11)',
                      }}
                      aria-hidden
                    />
                    <span className="ident text-[11px] font-semibold">{violation.rule_id}</span>
                    <Badge tone={violation.severity === 'block' ? 'err' : 'warn'}>
                      {violation.severity}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-[11px] text-[var(--text-primary)]">
                    {violation.rule_title}
                  </p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                    {violation.detail}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex items-start gap-2 p-4">
              <ShieldCheck size={15} className="mt-px text-[var(--ok-11)]" aria-hidden />
              <p className="text-[12px] text-[var(--text-secondary)]">
                This workflow lints clean against all sixteen rules.
              </p>
            </div>
          )}
        </Panel>

        {simulate.data ? (
          <Panel
            title="Simulation"
            subtitle={simulate.data.completed ? 'token completed' : 'token blocked'}
            className="max-h-[42%] shrink-0"
          >
            <ol className="p-2">
              {simulate.data.path.map((step, index) => (
                <li key={step.node_id} className="flex items-start gap-2 py-1 text-[11px]">
                  <span className="tnum w-4 shrink-0 text-[var(--text-tertiary)]">{index + 1}</span>
                  <span
                    className="mt-1 size-1.5 shrink-0 rounded-full"
                    style={{
                      background: step.status === 'blocked' ? 'var(--err-9)' : 'var(--ok-9)',
                    }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[var(--text-primary)]">{step.label}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">
                      {LANE_LABEL[step.lane] ?? step.lane} · {step.node_kind}
                      {step.persona ? ` · ${step.persona}` : ''}
                    </p>
                    {step.reason ? (
                      <p className="mt-0.5 text-[10px] text-[var(--err-11)]">{step.reason}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
        ) : (
          <Panel title="Rules" subtitle="LR1 to LR16" className="max-h-[42%] shrink-0">
            <ul className="p-2">
              {(rules.data ?? []).map((rule) => (
                <li key={rule.id} className="flex items-start gap-2 py-0.5 text-[11px]">
                  <span className="ident w-8 shrink-0 text-[var(--text-tertiary)]">{rule.id}</span>
                  <span className="min-w-0 flex-1 text-[var(--text-secondary)]">{rule.title}</span>
                  <Badge tone={rule.severity === 'block' ? 'err' : 'warn'}>{rule.severity}</Badge>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
    </div>
  );
}

/**
 * The swimlanes.
 *
 * Drawn inside the flow viewport rather than over it. An overlay in screen
 * space drifts out of register with the nodes as soon as the graph is panned
 * or zoomed, which in this product means a step appearing to sit in the wrong
 * office: precisely the thing the Studio exists to make unambiguous.
 */
function LaneBackdrop({ width }: { width: number }) {
  return (
    <ViewportPortal>
      <div style={{ position: 'absolute', top: 0, left: 0 }} aria-hidden>
        {LANES.map((lane, index) => (
          <div
            key={lane}
            style={{
              position: 'absolute',
              top: index * LANE_HEIGHT - 28,
              left: -80,
              width: width + 200,
              height: LANE_HEIGHT,
              borderTop: '1px dashed var(--border-subtle)',
              background:
                index % 2 === 0 ? 'color-mix(in srgb, var(--surface-2) 45%, transparent)' : 'transparent',
            }}
          >
            <span
              style={{
                position: 'absolute',
                top: 6,
                left: 86,
                fontSize: 10,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: 'var(--text-tertiary)',
                whiteSpace: 'nowrap',
              }}
            >
              {LANE_LABEL[lane]}
            </span>
          </div>
        ))}
      </div>
    </ViewportPortal>
  );
}

type StepData = {
  label: string;
  lane: string;
  kind: string;
  persona: string | null;
  violations: Violation[];
  isBlocked: boolean;
};

function StepNode({ data, selected }: NodeProps) {
  const step = data as unknown as StepData;
  const shape =
    step.kind === 'gate' || step.kind === 'approval'
      ? 'rounded-[14px]'
      : step.kind === 'start' || step.kind === 'end'
        ? 'rounded-full'
        : 'rounded-[3px]';

  return (
    <div
      className={cn('w-[168px] bg-[var(--surface-3)] px-2.5 py-1.5', shape)}
      style={{
        boxShadow: step.isBlocked
          ? 'inset 0 0 0 2px var(--err-9)'
          : selected
            ? 'inset 0 0 0 2px var(--focus-ring)'
            : 'inset 0 0 0 1px var(--border-interactive)',
        background: step.isBlocked ? 'var(--err-3)' : undefined,
      }}
      title={step.violations.map((v) => `${v.rule_id}: ${v.detail}`).join('\n') || undefined}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !bg-[var(--border-strong)]" />
      <div className="flex items-center gap-1">
        <span className="text-[9px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
          {step.kind}
        </span>
        {step.persona ? (
          <span className="ident ml-auto text-[9px] text-[var(--text-tertiary)]">
            {step.persona}
          </span>
        ) : null}
      </div>
      <p className="mt-0.5 text-[11px] leading-tight text-[var(--text-primary)]">{step.label}</p>
      {step.violations.length ? (
        <p className="mt-1 flex items-center gap-1 text-[9px] text-[var(--err-11)]">
          <ShieldAlert size={9} aria-hidden />
          {step.violations.map((v) => v.rule_id).join(', ')}
        </p>
      ) : null}
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !bg-[var(--border-strong)]" />
    </div>
  );
}

const stepNodeTypes = { step: StepNode };
