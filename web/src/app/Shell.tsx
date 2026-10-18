/**
 * The persistent shell.
 *
 * Switching register preserves the active entity, date, filters and persona.
 * That is the product's core interaction promise, and it works because the
 * register is a path segment while everything else lives in the query string.
 */

import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router';
import {
  Activity,
  BookOpen,
  Building2,
  Command,
  Network,
  Terminal as TerminalIcon,
} from 'lucide-react';
import { useAppState } from '@/lib/hooks';
import { setUsdToInr, useUi } from '@/lib/store';
import type { DisplayCurrency } from '@/lib/format';
import { Badge, Button, Dot, cn } from '@/components/primitives';
import { CommandPalette } from './CommandPalette';
import { ConsentBanner } from './ConsentBanner';

const REGISTERS = [
  { to: '/canvas', label: 'Canvas', icon: Network, hint: 'Node graph, eight lenses' },
  { to: '/console', label: 'Console', icon: Building2, hint: 'Estate map and banking register' },
  { to: '/terminal', label: 'Terminal', icon: TerminalIcon, hint: 'Ops console and blotters' },
  { to: '/brief', label: 'Brief', icon: BookOpen, hint: 'CFO narrative and KPIs' },
  { to: '/cockpit', label: 'Cockpit', icon: Activity, hint: 'Single-entity scoped view' },
] as const;

const DISPLAYS: DisplayCurrency[] = ['USD', 'INR', 'native'];

export function Shell() {
  const state = useAppState();
  const persona = useUi((s) => s.persona);
  const setPersona = useUi((s) => s.setPersona);
  const display = useUi((s) => s.display);
  const setDisplay = useUi((s) => s.setDisplay);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  // The INR toggle converts through the API's own rate, never an invented one.
  useEffect(() => {
    if (state.data) setUsdToInr(state.data.usd_to_inr);
  }, [state.data]);

  const entity = params.get('entity');
  const search = params.toString();

  const personaRecord = state.data?.persona;
  const stale = state.data?.summary
    ? state.data.summary.coverage.accounts_total - state.data.summary.coverage.accounts_current
    : 0;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[var(--surface-1)]">
      <header
        className="flex shrink-0 items-center gap-3 border-b border-[var(--border-subtle)] bg-[var(--surface-2)] px-3"
        style={{ height: 'var(--topbar-h)' }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-hidden
            className="grid size-[22px] place-items-center rounded-[3px] bg-[var(--accent-9)] text-[11px] font-bold text-white"
          >
            G
          </span>
          <span className="truncate text-[13px] font-semibold" translate="no">
            GCPL Treasury Command
          </span>
          <Badge tone="neutral" title="This is a Phase 0 control layer, not a TMS.">
            Phase 0 control layer
          </Badge>
        </div>

        <nav aria-label="Registers" className="flex items-center gap-0.5">
          {REGISTERS.map(({ to, label, icon: Icon, hint }) => {
            const target = to === '/cockpit' && entity ? `/cockpit/${entity}` : to;
            return (
              <NavLink
                key={to}
                to={{ pathname: target, search }}
                title={hint}
                className={({ isActive }) =>
                  cn(
                    'flex h-7 items-center gap-1.5 rounded-[3px] px-2.5 text-[12px] font-medium transition-colors duration-100',
                    isActive
                      ? 'bg-[var(--surface-4)] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--border-interactive)]'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]',
                  )
                }
              >
                <Icon size={13} aria-hidden />
                {label}
              </NavLink>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div
            role="group"
            aria-label="Display currency"
            className="flex overflow-hidden rounded-[3px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
          >
            {DISPLAYS.map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={display === option}
                onClick={() => setDisplay(option)}
                className={cn(
                  'h-7 px-2 text-[11px] font-medium transition-colors duration-100',
                  display === option
                    ? 'bg-[var(--surface-4)] text-[var(--text-primary)]'
                    : 'text-[var(--text-tertiary)] hover:bg-[var(--surface-3)] hover:text-[var(--text-primary)]',
                )}
              >
                <span translate="no">{option === 'native' ? 'Native' : option}</span>
              </button>
            ))}
          </div>

          <label className="sr-only" htmlFor="persona-switch">
            Acting persona
          </label>
          <select
            id="persona-switch"
            value={persona}
            onChange={(event) => setPersona(event.target.value)}
            title="Acting persona. Scope is resolved on the server from this value."
            className="h-7 rounded-[3px] px-2 text-[12px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
          >
            {PERSONA_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.id} · {option.label}
              </option>
            ))}
          </select>

          {personaRecord ? (
            <Badge
              tone={personaRecord.scope_kind === 'group' ? 'info' : 'accent'}
              title={`Scope resolved by the server: ${personaRecord.scope_kind}${
                personaRecord.scope_ref ? ` ${personaRecord.scope_ref}` : ''
              }`}
            >
              {personaRecord.scope_kind}
              {personaRecord.scope_ref ? ` · ${personaRecord.scope_ref}` : ''}
            </Badge>
          ) : null}

          <span
            className="flex items-center gap-1.5 text-[11px] text-[var(--text-tertiary)]"
            title={
              stale
                ? `${stale} account feeds are stale or offline and are shown with an age badge.`
                : 'Every account feed is current.'
            }
          >
            <Dot tone={stale ? 'warn' : 'ok'} title={stale ? 'Feeds degraded' : 'Feeds current'} />
            {stale ? `${stale} stale` : 'feeds current'}
          </span>

          <Button
            variant="ghost"
            onClick={() => navigate({ pathname: location.pathname, search }, { replace: true })}
            title="Command palette. Press Control or Command and K."
            className="gap-1"
          >
            <Command size={12} aria-hidden />
            <span className="ident">⌘&nbsp;K</span>
          </Button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>

      {/* Non-removable. A Playwright test asserts this is in the DOM on every route. */}
      <footer
        data-testid="watermark"
        className="flex shrink-0 items-center justify-center border-t border-[var(--border-subtle)] bg-[var(--surface-2)] text-[10px] tracking-[0.08em] text-[var(--text-tertiary)] uppercase"
        style={{ height: 'var(--ribbon-h)' }}
      >
        {state.data?.watermark ??
          'SYNTHETIC DATA // DEMO TENANT FOR EY CAFTA 2026 // DO NOT RELY FOR LIVE TRANSFERS'}
      </footer>

      <CommandPalette />
      <ConsentBanner />
    </div>
  );
}

/** The ten personas, for the switcher. Capabilities are enforced server-side. */
const PERSONA_OPTIONS = [
  { id: 'P1', label: 'CFO' },
  { id: 'P2', label: 'Group Treasurer' },
  { id: 'P3', label: 'Front Office Dealer' },
  { id: 'P4', label: 'Regional Lead' },
  { id: 'P5', label: 'Local Coordinator' },
  { id: 'P6', label: 'Risk and Control' },
  { id: 'P7', label: 'Operations' },
  { id: 'P8', label: 'Internal Auditor' },
  { id: 'P9', label: 'IT Administrator' },
  { id: 'P10', label: 'Tax and Legal' },
] as const;

