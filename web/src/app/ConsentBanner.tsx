/**
 * Storage consent.
 *
 * This application sets no cookies and loads no third-party script, so there is
 * nothing here to consent to on anyone else's behalf. What it does do is keep
 * two preferences — the acting persona and the display currency — in this
 * browser's local storage. That is what the notice describes, in those words.
 *
 * Declining is a real choice: the store's guarded adapter refuses to write, and
 * the preferences simply reset on reload.
 */

import { Cookie } from 'lucide-react';
import { useUi } from '@/lib/store';
import { Button } from '@/components/primitives';

export function ConsentBanner() {
  const consent = useUi((state) => state.consent);
  const setConsent = useUi((state) => state.setConsent);

  if (consent !== 'unknown') return null;

  return (
    <aside
      role="region"
      aria-label="Storage notice"
      className="animate-fade fixed bottom-[calc(var(--ribbon-h)+12px)] left-1/2 z-40 w-[min(620px,92vw)] -translate-x-1/2 rounded-[6px] bg-[var(--surface-3)] p-3 shadow-[inset_0_0_0_1px_var(--border-strong),0_8px_24px_rgba(0,0,0,0.45)]"
    >
      <div className="flex items-start gap-3">
        <Cookie size={16} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-[var(--text-primary)]">
            This demo sets no cookies and loads no third-party analytics. It can keep two
            preferences in this browser: your acting persona and your display currency.
          </p>
          <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">
            Decline and the app works exactly the same; those two choices just reset when you
            reload. See the{' '}
            <a href="/privacy.html" target="_blank" rel="noreferrer">
              privacy notice
            </a>
            .
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button variant="ghost" onClick={() => setConsent('declined')}>
            Decline
          </Button>
          <Button variant="primary" onClick={() => setConsent('granted')}>
            Allow
          </Button>
        </div>
      </div>
    </aside>
  );
}
