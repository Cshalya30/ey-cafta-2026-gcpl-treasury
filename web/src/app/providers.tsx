/** Query client and URL-state provider. */

import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NuqsAdapter } from 'nuqs/adapters/react-router/v7';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Treasury data changes on a daily cycle, not a second-by-second one.
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // A 403 is an access decision, not a transient fault: never retry it.
      retry: (failureCount, error) => {
        const status = (error as { status?: number }).status;
        if (status === 403 || status === 404) return false;
        return failureCount < 2;
      },
    },
  },
});

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <NuqsAdapter>{children}</NuqsAdapter>
    </QueryClientProvider>
  );
}
