/** Node cards for the Canvas graph. */

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Figure } from '@/components/Figure';
import { Dot, RouteBadge, cn } from '@/components/primitives';
import type { LensReading } from './lenses';
import type { Entity } from '@/lib/types';

export type EntityNodeData = {
  entity: Entity;
  reading: LensReading;
  lensLabel: string;
  isolated: boolean;
  dimmed: boolean;
};

export function EntityNode({ data, selected }: NodeProps) {
  const { entity, reading, lensLabel, dimmed } = data as unknown as EntityNodeData;

  return (
    <div
      className={cn(
        'w-[208px] rounded-[4px] bg-[var(--surface-2)] px-2.5 py-2 transition-opacity duration-150',
        dimmed && 'opacity-25',
      )}
      style={{
        boxShadow: selected
          ? 'inset 0 0 0 2px var(--focus-ring)'
          : 'inset 0 0 0 1px var(--border-subtle)',
      }}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !bg-[var(--border-strong)]" />

      <div className="flex items-center gap-1.5">
        <Dot tone={reading.tone} title={`${lensLabel}: ${reading.state}`} />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold" translate="no">
          {entity.short_name}
        </span>
        <RouteBadge route={entity.route} />
      </div>

      <div className="mt-1 flex items-baseline justify-between gap-2">
        <span className="ident truncate text-[10px] text-[var(--text-tertiary)]">{entity.id}</span>
        <span
          className="tnum shrink-0 text-[11px] font-semibold"
          title={reading.badgeLabel}
          aria-label={reading.badgeLabel}
        >
          {reading.badge}
        </span>
      </div>

      {/* A second, non-colour encoding of the same magnitude. */}
      <div
        className="mt-1.5 h-[3px] w-full overflow-hidden rounded-full bg-[var(--surface-4)]"
        role="presentation"
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round(reading.magnitude * 100)}%`,
            background:
              reading.tone === 'ok'
                ? 'var(--ok-9)'
                : reading.tone === 'warn'
                  ? 'var(--warn-9)'
                  : reading.tone === 'err'
                    ? 'var(--err-9)'
                    : 'var(--stale-9)',
          }}
        />
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px] text-[var(--text-tertiary)]">
        <span className="truncate">{reading.state}</span>
        <Figure
          value={entity.decomposition.deployable_surplus}
          compact
          className="shrink-0 text-[10px]"
        />
      </div>

      <Handle type="source" position={Position.Bottom} className="!size-1.5 !bg-[var(--border-strong)]" />
    </div>
  );
}

export type GroupNodeData = {
  label: string;
  sub: string;
  kind: 'root' | 'hub';
  dimmed: boolean;
};

export function GroupNode({ data }: NodeProps) {
  const { label, sub, kind, dimmed } = data as unknown as GroupNodeData;
  return (
    <div
      className={cn(
        'rounded-[4px] px-3 py-2 text-center transition-opacity duration-150',
        kind === 'root' ? 'w-[236px] bg-[var(--surface-4)]' : 'w-[200px] bg-[var(--surface-3)]',
        dimmed && 'opacity-25',
      )}
      style={{
        boxShadow:
          kind === 'root'
            ? 'inset 0 0 0 1px var(--accent-9)'
            : 'inset 0 0 0 1px var(--border-interactive)',
      }}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !bg-[var(--border-strong)]" />
      <p className="truncate text-[12px] font-semibold" translate="no">
        {label}
      </p>
      <p className="truncate text-[10px] text-[var(--text-tertiary)]">{sub}</p>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !bg-[var(--border-strong)]" />
    </div>
  );
}

export const nodeTypes = { entity: EntityNode, group: GroupNode };
