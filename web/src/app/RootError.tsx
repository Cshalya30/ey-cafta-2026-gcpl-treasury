/** Router-level error boundary. In place, with a retry, and never a stack trace. */

import { useRouteError, Link } from 'react-router';
import { AlertTriangle } from 'lucide-react';

export function RootError() {
  const error = useRouteError();
  // The message is logged for the developer console only; the reader gets prose.
  if (import.meta.env.DEV) console.error(error);

  return (
    <div className="flex h-dvh items-center justify-center bg-[var(--surface-1)] p-6">
      <div
        role="alert"
        className="max-w-[60ch] rounded-[6px] p-5"
        style={{ background: 'var(--err-3)', boxShadow: 'inset 0 0 0 1px var(--err-9)' }}
      >
        <AlertTriangle size={18} style={{ color: 'var(--err-11)' }} aria-hidden />
        <h1 className="mt-2 text-[17px] font-semibold">This register could not be rendered.</h1>
        <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
          Nothing was changed. Check that the API is running on port 8000, then reload. If the
          database is missing, regenerate it with the seed command in the README.
        </p>
        <Link
          to="/canvas"
          className="mt-4 inline-flex h-7 items-center rounded-[3px] bg-[var(--surface-3)] px-3 text-[12px] text-[var(--text-primary)] no-underline shadow-[inset_0_0_0_1px_var(--border-interactive)]"
        >
          Back to Canvas
        </Link>
      </div>
    </div>
  );
}
