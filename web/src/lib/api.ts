/**
 * The API client. All server access goes through here and through TanStack
 * Query; there is no useEffect fetching anywhere in src/.
 *
 * Scope is never filtered in the browser. This client sends the acting persona
 * and renders whatever the server decides to return, including its 403s.
 */

import type { Problem } from './types';

const BASE = '/api/v1';

export class ApiError extends Error {
  readonly problem: Problem;
  readonly status: number;

  constructor(problem: Problem) {
    super(problem.title);
    this.name = 'ApiError';
    this.problem = problem;
    this.status = problem.status;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }
}

function problemFrom(status: number, body: unknown, path: string): Problem {
  if (body && typeof body === 'object' && 'title' in body && 'status' in body) {
    return body as Problem;
  }
  return {
    type: 'about:blank',
    title: status === 0 ? 'The API is unreachable.' : 'The request failed.',
    status,
    detail:
      status === 0
        ? 'No response from the API. Check that uvicorn is running on port 8000.'
        : 'The server returned an unexpected response.',
    instance: path,
  };
}

const CSRF_COOKIE = 'gcpl_csrf';

/**
 * The readable half of the double-submit CSRF pair.
 *
 * Absent in development, where the API does not enforce it. Reading it is
 * wrapped because document.cookie can throw with blocked site data.
 */
function csrfToken(): string | null {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
    return match?.[1] ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  persona: string,
  init?: RequestInit & { body?: string },
): Promise<T> {
  const csrf = init?.method === 'POST' ? csrfToken() : null;
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        'X-Persona': persona,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
        ...init?.headers,
      },
      // Same-origin only: the dev server proxies /api, so no cross-origin
      // credentialled request is ever made from the browser.
      credentials: 'same-origin',
    });
  } catch {
    throw new ApiError(problemFrom(0, null, path));
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(problemFrom(response.status, body, path));
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, persona: string) => request<T>(path, persona),
  post: <T>(path: string, persona: string, body: unknown) =>
    request<T>(path, persona, { method: 'POST', body: JSON.stringify(body) }),
};

/** Query keys. The persona is part of every key: scope changes the payload. */
export const keys = {
  state: (p: string) => ['state', p] as const,
  personas: (p: string) => ['personas', p] as const,
  entities: (p: string, filters?: string) => ['entities', p, filters ?? ''] as const,
  entity: (p: string, id: string) => ['entity', p, id] as const,
  groupView: (p: string, id: string) => ['group-view', p, id] as const,
  onboarding: (p: string, id: string) => ['onboarding', p, id] as const,
  accounts: (p: string, filters?: string) => ['accounts', p, filters ?? ''] as const,
  banks: (p: string) => ['banks', p] as const,
  coverage: (p: string) => ['coverage-matrix', p] as const,
  balances: (p: string, asOf?: string) => ['balances', p, asOf ?? ''] as const,
  facilities: (p: string) => ['facilities', p] as const,
  forecasts: (p: string, id: string) => ['forecasts', p, id] as const,
  pools: (p: string) => ['pools', p] as const,
  cashLeak: (p: string) => ['cash-leak', p] as const,
  proposals: (p: string, status?: string) => ['proposals', p, status ?? ''] as const,
  proposal: (p: string, id: string) => ['proposal', p, id] as const,
  workflows: (p: string) => ['workflows', p] as const,
  workflow: (p: string, id: string) => ['workflow', p, id] as const,
  simulation: (p: string, id: string) => ['simulation', p, id] as const,
  rules: (p: string) => ['sod-rules', p] as const,
  audit: (p: string, filters?: string) => ['audit', p, filters ?? ''] as const,
  chain: (p: string) => ['chain', p] as const,
  kpis: (p: string) => ['kpis', p] as const,
  waves: (p: string) => ['waves', p] as const,
  routes: (p: string) => ['routes', p] as const,
  notional: (p: string) => ['notional-pooling', p] as const,
  exposures: (p: string, id?: string) => ['exposures', p, id ?? ''] as const,
};

export function queryString(params: Record<string, string | undefined | null>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string] => Boolean(entry[1]),
  );
  return entries.length ? `?${new URLSearchParams(entries).toString()}` : '';
}
