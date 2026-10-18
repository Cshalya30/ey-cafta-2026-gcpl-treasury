/** Custom 404. Names where the reader is and offers the way back. */

import { Link, useLocation, useSearchParams } from 'react-router';
import { Compass } from 'lucide-react';

export function NotFound() {
  const location = useLocation();
  const [params] = useSearchParams();
  const search = params.toString();

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-[56ch]">
        <Compass size={22} className="mb-3 text-[var(--text-tertiary)]" aria-hidden />
        <h1 className="text-[20px] font-semibold">That register does not exist.</h1>
        <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
          Nothing is served at <code className="ident">{location.pathname}</code>. The five
          registers are Canvas, Console, Terminal, Brief and Cockpit.
        </p>
        <nav className="mt-4 flex flex-wrap gap-2" aria-label="Registers">
          {[
            ['/canvas', 'Canvas'],
            ['/console', 'Console'],
            ['/terminal', 'Terminal'],
            ['/brief', 'Brief'],
          ].map(([to, label]) => (
            <Link
              key={to}
              to={{ pathname: to, search }}
              className="inline-flex h-7 items-center rounded-[3px] bg-[var(--surface-3)] px-3 text-[12px] text-[var(--text-primary)] no-underline shadow-[inset_0_0_0_1px_var(--border-interactive)] hover:bg-[var(--surface-4)]"
            >
              {label}
            </Link>
          ))}
        </nav>
        <p className="mt-4 text-[11px] text-[var(--text-tertiary)]">
          Your entity selection and persona are preserved in the link above.
        </p>
      </div>
    </div>
  );
}
