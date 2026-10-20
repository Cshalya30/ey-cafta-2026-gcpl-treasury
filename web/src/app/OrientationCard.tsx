/**
 * First-visit orientation.
 *
 * A judge arrives with no briefing. This says what the system is, states the
 * data is synthetic, and hands over three deep links rather than asking them
 * to find the one register that explains everything. Dismissal persists the
 * same way every other preference here does: through the consent-gated
 * store, which already renders correctly when storage is absent or throws.
 */

import { Link } from 'react-router';
import { Compass, X } from 'lucide-react';
import { useUi } from '@/lib/store';
import { Button } from '@/components/primitives';

const LINKS = [
  { to: '/canvas?lens=cash', label: 'See group cash in one lens' },
  { to: '/canvas/pooling?source=GCPL-JP&target=GCPL-IN', label: 'Propose a pooling sweep' },
  { to: '/method', label: 'See how the system works' },
] as const;

export function OrientationCard() {
  const dismissed = useUi((state) => state.orientationDismissed);
  const setDismissed = useUi((state) => state.setOrientationDismissed);

  if (dismissed) return null;

  return (
    <aside
      role="region"
      aria-label="Orientation"
      className="animate-fade fixed top-[calc(var(--topbar-h)+12px)] left-1/2 z-40 w-[min(620px,92vw)] -translate-x-1/2 rounded-[6px] bg-[var(--surface-3)] p-3 shadow-[inset_0_0_0_1px_var(--border-strong),0_8px_24px_rgba(0,0,0,0.45)]"
    >
      <div className="flex items-start gap-3">
        <Compass size={16} className="mt-0.5 shrink-0 text-[var(--accent-9)]" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-[var(--text-primary)]">
            This is a Phase 0 cash visibility and pooling control layer for GCPL treasury, not a
            Treasury Management System: it proposes and records, it never moves money. Every
            figure on screen is synthetic demo data.
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setDismissed(true)}
                className="rounded-[3px] bg-[var(--surface-4)] px-2 py-1 text-[11px] font-medium text-[var(--text-primary)] no-underline shadow-[inset_0_0_0_1px_var(--border-interactive)] hover:bg-[var(--surface-2)]"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <Button
          variant="ghost"
          onClick={() => setDismissed(true)}
          title="Dismiss. Reopen any time from the compass in the header."
          className="shrink-0 px-1.5"
        >
          <X size={14} aria-hidden />
          <span className="sr-only">Dismiss orientation</span>
        </Button>
      </div>
    </aside>
  );
}
