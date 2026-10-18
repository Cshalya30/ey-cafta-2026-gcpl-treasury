/**
 * Command palette. Opens on Control-K or Command-K.
 *
 * Every entry is a deep link, because treasury users paste views to approvers
 * and a command that cannot be pasted is a command that has to be repeated.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CornerDownLeft, Search } from 'lucide-react';
import { useEntities, useWorkflows } from '@/lib/hooks';
import { useUi } from '@/lib/store';
import { cn } from '@/components/primitives';

type Command = {
  id: string;
  label: string;
  group: string;
  hint?: string;
  run: () => void;
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setPersona = useUi((s) => s.setPersona);
  const setDisplay = useUi((s) => s.setDisplay);

  const entities = useEntities();
  const workflows = useWorkflows();
  const search = params.toString();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((previous) => !previous);
      }
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => {
      navigate({ pathname: path, search });
      setOpen(false);
    };

    const list: Command[] = [
      { id: 'r-canvas', group: 'Register', label: 'Canvas', hint: 'Node graph, eight lenses', run: go('/canvas') },
      { id: 'r-pool', group: 'Register', label: 'Pooling Workbench', run: go('/canvas/pooling') },
      { id: 'r-console', group: 'Register', label: 'Console', hint: 'Estate and banking register', run: go('/console') },
      { id: 'r-terminal', group: 'Register', label: 'Terminal', hint: 'Blotters and audit stream', run: go('/terminal') },
      { id: 'r-brief', group: 'Register', label: 'Brief', hint: 'CFO narrative and KPIs', run: go('/brief') },
    ];

    for (const lens of LENSES) {
      list.push({
        id: `lens-${lens.key}`,
        group: 'Lens',
        label: `${lens.key}. ${lens.label}`,
        hint: lens.hint,
        run: () => {
          const next = new URLSearchParams(search);
          next.set('lens', lens.id);
          navigate({ pathname: '/canvas', search: next.toString() });
          setOpen(false);
        },
      });
    }

    for (const entity of entities.data ?? []) {
      list.push({
        id: `e-${entity.id}`,
        group: 'Entity',
        label: `${entity.short_name} (${entity.id})`,
        hint: `${entity.country_name} · Route ${entity.route}`,
        run: () => {
          const next = new URLSearchParams(search);
          next.set('entity', entity.id);
          navigate({ pathname: '/canvas', search: next.toString() });
          setOpen(false);
        },
      });
    }

    for (const workflow of workflows.data ?? []) {
      list.push({
        id: `w-${workflow.id}`,
        group: 'Workflow',
        label: `${workflow.id} ${workflow.name}`,
        hint: workflow.violation_count
          ? `${workflow.violation_count} violation(s)`
          : 'lints clean',
        run: go(`/canvas/workflow/${workflow.id}`),
      });
    }

    for (const persona of PERSONAS) {
      list.push({
        id: `p-${persona.id}`,
        group: 'Persona',
        label: `Act as ${persona.label} (${persona.id})`,
        run: () => {
          setPersona(persona.id);
          setOpen(false);
        },
      });
    }

    for (const option of ['USD', 'INR', 'native'] as const) {
      list.push({
        id: `c-${option}`,
        group: 'Currency',
        label: `Show figures in ${option === 'native' ? 'native currency' : option}`,
        run: () => {
          setDisplay(option);
          setOpen(false);
        },
      });
    }

    return list;
  }, [entities.data, workflows.data, navigate, search, setPersona, setDisplay]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands.slice(0, 40);
    return commands
      .filter((command) =>
        `${command.group} ${command.label} ${command.hint ?? ''}`.toLowerCase().includes(needle),
      )
      .slice(0, 40);
  }, [commands, query]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      className="animate-fade fixed inset-0 z-50 flex items-start justify-center bg-black/55 pt-[12vh]"
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="animate-palette w-[min(640px,92vw)] overflow-hidden rounded-[6px] bg-[var(--surface-2)] shadow-[inset_0_0_0_1px_var(--border-strong)]"
      >
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-3">
          <Search size={14} className="text-[var(--text-tertiary)]" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault();
                setActive((index) => Math.min(index + 1, filtered.length - 1));
              }
              if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive((index) => Math.max(index - 1, 0));
              }
              if (event.key === 'Enter') {
                event.preventDefault();
                filtered[active]?.run();
              }
            }}
            placeholder="Jump to a register, lens, entity, workflow or persona…"
            aria-label="Search commands"
            className="h-11 flex-1 bg-transparent text-[13px] outline-none placeholder:text-[var(--text-tertiary)]"
          />
          <kbd className="ident rounded-[3px] bg-[var(--surface-4)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
            Esc
          </kbd>
        </div>

        <ul
          role="listbox"
          aria-label="Commands"
          tabIndex={-1}
          className="max-h-[52vh] overflow-auto py-1"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-4 text-[12px] text-[var(--text-tertiary)]">
              Nothing matches “{query}”. Try an entity id, a lens number or a persona.
            </li>
          ) : (
            filtered.map((command, index) => (
              <li key={command.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === active}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => command.run()}
                  className={cn(
                    'flex w-full items-center gap-2 px-3 text-left text-[12px]',
                    'h-8',
                    index === active
                      ? 'bg-[var(--surface-4)] text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)]',
                  )}
                >
                  <span className="w-[72px] shrink-0 text-[10px] tracking-[0.06em] text-[var(--text-tertiary)] uppercase">
                    {command.group}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{command.label}</span>
                  {command.hint ? (
                    <span className="shrink-0 truncate text-[11px] text-[var(--text-tertiary)]">
                      {command.hint}
                    </span>
                  ) : null}
                  {index === active ? (
                    <CornerDownLeft size={11} className="shrink-0 text-[var(--text-tertiary)]" aria-hidden />
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}

export const LENSES = [
  { key: 1, id: 'cash', label: 'Cash', hint: 'Deployable surplus and the leak' },
  { key: 2, id: 'forecast', label: '13-week forecast', hint: 'Net position at week four' },
  { key: 3, id: 'pooling', label: 'Funding and pooling', hint: 'Pool flows and routes' },
  { key: 4, id: 'risk', label: 'Risk and exposure', hint: 'Unhedged ratio' },
  { key: 5, id: 'controls', label: 'Controls and SoD', hint: 'Open breaches' },
  { key: 6, id: 'data', label: 'Data health', hint: 'Feed staleness' },
  { key: 7, id: 'banking', label: 'Banking', hint: 'Distinct banks per entity' },
  { key: 8, id: 'service', label: 'Service (SLA)', hint: 'Attainment and response' },
] as const;

const PERSONAS = [
  { id: 'P1', label: 'CFO' },
  { id: 'P2', label: 'Group Treasurer' },
  { id: 'P3', label: 'Front Office Dealer' },
  { id: 'P4', label: 'Regional Lead' },
  { id: 'P5', label: 'Local Coordinator' },
  { id: 'P6', label: 'Risk and Control Analyst' },
  { id: 'P7', label: 'Operations Specialist' },
  { id: 'P8', label: 'Internal Auditor' },
  { id: 'P9', label: 'IT Administrator' },
  { id: 'P10', label: 'Tax and Legal Counsel' },
] as const;
