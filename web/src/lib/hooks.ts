/** Typed query hooks. Every server read in the app goes through one of these. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, keys, queryString } from './api';
import { useUi } from './store';
import type {
  Account,
  AppState,
  AuditEvent,
  Balance,
  Bank,
  CashLeak,
  Chain,
  CoverageMatrix,
  Entity,
  Evaluation,
  Exposure,
  Facility,
  Forecast,
  GroupView,
  Kpi,
  NotionalPooling,
  OnboardingItem,
  Persona,
  Pool,
  Programme,
  Proposal,
  Route,
  ScoreResponse,
  Simulation,
  SodRule,
  Workflow,
  WorkflowDetail,
} from './types';

export const usePersona = (): string => useUi((state) => state.persona);

export function useAppState() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.state(persona),
    queryFn: () => api.get<AppState>('/state', persona),
  });
}

export function usePersonas() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.personas(persona),
    queryFn: () => api.get<Persona[]>('/personas', persona),
    staleTime: Infinity,
  });
}

export function useEntities(filters: Record<string, string | null> = {}) {
  const persona = usePersona();
  const qs = queryString(filters);
  return useQuery({
    queryKey: keys.entities(persona, qs),
    queryFn: () => api.get<Entity[]>(`/entities${qs}`, persona),
  });
}

export function useEntity(id: string | null) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.entity(persona, id ?? ''),
    queryFn: () => api.get<Entity>(`/entities/${id}`, persona),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useGroupView(id: string | null) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.groupView(persona, id ?? ''),
    queryFn: () => api.get<GroupView>(`/entities/${id}/group-view`, persona),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useOnboarding(id: string | null) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.onboarding(persona, id ?? ''),
    queryFn: () => api.get<OnboardingItem[]>(`/entities/${id}/onboarding`, persona),
    enabled: Boolean(id),
  });
}

export function useAccounts(filters: Record<string, string | null> = {}) {
  const persona = usePersona();
  const qs = queryString(filters);
  return useQuery({
    queryKey: keys.accounts(persona, qs),
    queryFn: () => api.get<Account[]>(`/accounts${qs}`, persona),
  });
}

export function useBanks() {
  const persona = usePersona();
  return useQuery({ queryKey: keys.banks(persona), queryFn: () => api.get<Bank[]>('/banks', persona) });
}

export function useCoverageMatrix() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.coverage(persona),
    queryFn: () => api.get<CoverageMatrix>('/banks/coverage-matrix', persona),
  });
}

export function useBalances(asOf?: string) {
  const persona = usePersona();
  const qs = queryString({ as_of: asOf ?? null });
  return useQuery({
    queryKey: keys.balances(persona, qs),
    queryFn: () => api.get<Balance[]>(`/balances${qs}`, persona),
  });
}

export function useFacilities() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.facilities(persona),
    queryFn: () => api.get<Facility[]>('/facilities', persona),
  });
}

export function useForecasts(entityId: string | null) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.forecasts(persona, entityId ?? ''),
    queryFn: () => api.get<Forecast[]>(`/forecasts/${entityId}`, persona),
    enabled: Boolean(entityId),
    retry: false,
  });
}

export function usePools() {
  const persona = usePersona();
  return useQuery({ queryKey: keys.pools(persona), queryFn: () => api.get<Pool[]>('/pools', persona) });
}

export function useCashLeak() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.cashLeak(persona),
    queryFn: () => api.get<CashLeak>('/cash-leak', persona),
  });
}

export function useProposals(status?: string) {
  const persona = usePersona();
  const qs = queryString({ status: status ?? null });
  return useQuery({
    queryKey: keys.proposals(persona, qs),
    queryFn: () => api.get<Proposal[]>(`/proposals${qs}`, persona),
  });
}

export function useWorkflows() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.workflows(persona),
    queryFn: () => api.get<Workflow[]>('/workflows', persona),
  });
}

export function useWorkflow(id: string | null) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.workflow(persona, id ?? ''),
    queryFn: () => api.get<WorkflowDetail>(`/workflows/${id}`, persona),
    enabled: Boolean(id),
  });
}

export function useSodRules() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.rules(persona),
    queryFn: () => api.get<SodRule[]>('/sod-rules', persona),
    staleTime: Infinity,
  });
}

export function useAudit(filters: Record<string, string | null> = {}) {
  const persona = usePersona();
  const qs = queryString(filters);
  return useQuery({
    queryKey: keys.audit(persona, qs),
    queryFn: () => api.get<AuditEvent[]>(`/audit${qs}`, persona),
  });
}

export function useChain(enabled = false) {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.chain(persona),
    queryFn: () => api.get<Chain>('/audit/verify', persona),
    enabled,
  });
}

export function useKpis() {
  const persona = usePersona();
  return useQuery({ queryKey: keys.kpis(persona), queryFn: () => api.get<Kpi[]>('/kpis', persona) });
}

export function useProgramme() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.waves(persona),
    queryFn: () => api.get<Programme>('/waves', persona),
  });
}

export function useRoutes() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.routes(persona),
    queryFn: () => api.get<Route[]>('/routes', persona),
    staleTime: Infinity,
  });
}

export function useNotionalPooling() {
  const persona = usePersona();
  return useQuery({
    queryKey: keys.notional(persona),
    queryFn: () => api.get<NotionalPooling>('/routes/notional-pooling', persona),
    staleTime: Infinity,
  });
}

export function useExposures(entityId?: string) {
  const persona = usePersona();
  const qs = queryString({ entity: entityId ?? null });
  return useQuery({
    queryKey: keys.exposures(persona, qs),
    queryFn: () => api.get<Exposure[]>(`/exposures${qs}`, persona),
  });
}

// ───────────────────────── mutations ─────────────────────────

export type EvaluateInput = {
  source_entity_id: string;
  target_entity_id: string;
  amount_usd: number;
  tenor_days: number;
  interest_rate: number;
  kind?: string;
  rating_band?: string;
};

export function useEvaluate() {
  const persona = usePersona();
  return useMutation({
    mutationFn: (input: EvaluateInput) =>
      api.post<Evaluation>('/proposals/evaluate', persona, input),
  });
}

export function useCreateProposal() {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: EvaluateInput & { rate_basis: string; justification: string }) =>
      api.post<Proposal>('/proposals', persona, input),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['proposals'] });
      void client.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}

export function useDecideProposal(action: 'approve' | 'settle') {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, justification }: { id: string; justification: string }) =>
      api.post<Proposal>(`/proposals/${id}/${action}`, persona, { justification }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['proposals'] });
      void client.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}

export function useLintWorkflow() {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<WorkflowDetail>(`/workflows/${id}/lint`, persona, {}),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['workflow'] });
      void client.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useMoveNode() {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { workflowId: string; node_id: string; lane: string; pos_x: number; pos_y: number }) =>
      api.post<WorkflowDetail>(`/workflows/${input.workflowId}/nodes/move`, persona, {
        node_id: input.node_id,
        lane: input.lane,
        pos_x: input.pos_x,
        pos_y: input.pos_y,
      }),
    onSuccess: (data) => {
      client.setQueryData(keys.workflow(persona, data.id), data);
      void client.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useSimulate() {
  const persona = usePersona();
  return useMutation({
    mutationFn: (id: string) => api.post<Simulation>(`/workflows/${id}/simulate`, persona, {}),
  });
}

export function useScoreEstate() {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { entity_id?: string; bank_id?: string; persist: boolean }) =>
      api.post<ScoreResponse>('/accounts/score', persona, input),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['accounts'] }),
  });
}

export function useSubmitForecast() {
  const persona = usePersona();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      entityId: string;
      cycle_year: number;
      cycle_week: number;
      lines: { week_offset: number; category: string; amount_native: number }[];
      justification: string;
    }) =>
      api.post<Forecast>(`/forecasts/${input.entityId}`, persona, {
        cycle_year: input.cycle_year,
        cycle_week: input.cycle_week,
        lines: input.lines,
        justification: input.justification,
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['forecasts'] });
      void client.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}
