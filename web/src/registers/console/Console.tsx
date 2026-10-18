/**
 * CONSOLE — the estate architecture map and the banking register.
 *
 * The 81-account table is the densest surface in the product: virtualized,
 * frozen header and identifier column, with sort and filter state in the URL
 * so a view survives a reload and can be pasted to an approver.
 */

import { useMemo, useState } from 'react';
import { useQueryState } from 'nuqs';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { Calculator, Search } from 'lucide-react';
import {
  useAccounts,
  useAppState,
  useBanks,
  useCoverageMatrix,
  useEntities,
  useScoreEstate,
} from '@/lib/hooks';
import { Badge, Button, Dot, Panel, RouteBadge, Stat, cn } from '@/components/primitives';
import { CoverageNote, ErrorState, FilteredEmpty, SkeletonRows, StaleBadge } from '@/components/states';
import { DataTable } from '@/components/DataTable';
import { Figure, UsdFigure } from '@/components/Figure';
import { date, pct, titleCase } from '@/lib/format';
import { Entity360 } from '@/features/entity360/Entity360';
import type { Account } from '@/lib/types';

const TABS = ['architecture', 'accounts', 'banks', 'coverage', 'feeds'] as const;

export function Console() {
  const [tab, setTab] = useQueryState('tab', { defaultValue: 'architecture' });
  const [entityId, setEntityId] = useQueryState('entity', { defaultValue: '' });

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <nav
          role="tablist"
          aria-label="Console sections"
          className="flex shrink-0 gap-1 border-b border-[var(--border-subtle)] bg-[var(--surface-2)] px-2 py-1.5"
        >
          {TABS.map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              onClick={() => void setTab(name)}
              className={cn(
                'h-7 rounded-[3px] px-2.5 text-[12px] transition-colors duration-100',
                tab === name
                  ? 'bg-[var(--surface-4)] text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--border-interactive)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--surface-3)]',
              )}
            >
              {titleCase(name)}
            </button>
          ))}
        </nav>

        <div
          role="tabpanel"
          tabIndex={0}
          aria-label={`Console: ${tab}`}
          className="min-h-0 flex-1 overflow-auto p-2"
        >
          {tab === 'architecture' ? (
            <Architecture onSelect={(id) => void setEntityId(id)} />
          ) : tab === 'accounts' ? (
            <BankingRegister onSelect={(id) => void setEntityId(id)} />
          ) : tab === 'banks' ? (
            <BankPanel />
          ) : tab === 'coverage' ? (
            <CoverageGrid />
          ) : (
            <Feeds />
          )}
        </div>
      </div>

      <Entity360 entityId={entityId || null} onClose={() => void setEntityId('')} />
    </div>
  );
}

function Architecture({ onSelect }: { onSelect: (id: string) => void }) {
  const state = useAppState();
  const entities = useEntities();

  if (entities.isPending || state.isPending) return <SkeletonRows rows={12} cols={5} />;
  if (entities.error) return <ErrorState error={entities.error} onRetry={() => entities.refetch()} />;

  const summary = state.data?.summary;

  return (
    <div className="space-y-2">
      {summary ? (
        <Panel title="Group position" subtitle={`as at ${date(summary.as_of)}`}>
          <div className="grid grid-cols-6 gap-4 p-3">
            <Stat label="Total cash" value={<Figure value={summary.total_cash} compact />} />
            <Stat
              label="Available local"
              value={<Figure value={summary.available_local} compact />}
            />
            <Stat
              label="Operating buffer"
              value={<Figure value={summary.operating_buffer} compact />}
              tone="info"
            />
            <Stat
              label="Deployable surplus"
              value={<Figure value={summary.deployable_surplus} compact />}
              tone="ok"
            />
            <Stat label="Restricted" value={<Figure value={summary.restricted} compact />} tone="warn" />
            <Stat label="Drawn debt" value={<Figure value={summary.drawn} compact />} tone="err" />
          </div>
          <div className="border-t border-[var(--border-subtle)] px-3 py-1.5">
            <CoverageNote coverage={summary.coverage} />
          </div>
        </Panel>
      ) : null}

      {(state.data?.regions ?? []).map((region) => {
        const members = (entities.data ?? []).filter((e) => e.region_id === region.id);
        if (!members.length) return null;
        return (
          <Panel
            key={region.id}
            title={region.name}
            subtitle={`${region.hub_city} · ${region.hub_lead} · ${region.coverage_hours} · ${titleCase(region.mandate)} mandate`}
          >
            <table className="grid-table">
              <thead>
                <tr>
                  <th scope="col" className="freeze-col">Entity</th>
                  <th scope="col">Country</th>
                  <th scope="col">ERP</th>
                  <th scope="col">Route</th>
                  <th scope="col">Pool</th>
                  <th scope="col" className="num">Accounts</th>
                  <th scope="col" className="num">Deployable</th>
                  <th scope="col" className="num">Drawn</th>
                  <th scope="col">Feeds</th>
                </tr>
              </thead>
              <tbody>
                {members.map((entity) => (
                  <tr
                    key={entity.id}
                    tabIndex={0}
                    onClick={() => onSelect(entity.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') onSelect(entity.id);
                    }}
                    className="cursor-pointer"
                  >
                    <td className="freeze-col">
                      <span className="flex items-center gap-1.5">
                        <span className="truncate" translate="no">{entity.short_name}</span>
                        {entity.is_hq ? <Badge tone="accent">HQ</Badge> : null}
                      </span>
                    </td>
                    <td>{entity.country_name}</td>
                    <td translate="no">{entity.erp_system}</td>
                    <td><RouteBadge route={entity.route} /></td>
                    <td>
                      <Badge
                        tone={
                          entity.pool_status === 'eligible'
                            ? 'ok'
                            : entity.pool_status === 'review'
                              ? 'warn'
                              : entity.pool_status === 'restricted'
                                ? 'err'
                                : 'neutral'
                        }
                      >
                        {titleCase(entity.pool_status)}
                      </Badge>
                    </td>
                    <td className="num tnum">{entity.account_count}</td>
                    <td className="num tnum">
                      <Figure value={entity.decomposition.deployable_surplus} compact />
                    </td>
                    <td className="num tnum"><Figure value={entity.drawn} compact /></td>
                    <td>
                      <span className="flex items-center gap-1">
                        <Dot
                          tone={entity.coverage_pct === 1 ? 'ok' : 'warn'}
                          title={`${entity.live_accounts} of ${entity.account_count} current`}
                        />
                        <span className="tnum text-[11px]">{pct(entity.coverage_pct, 0)}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        );
      })}
    </div>
  );
}

function BankingRegister({ onSelect }: { onSelect: (id: string) => void }) {
  const [entityFilter, setEntityFilter] = useQueryState('acct_entity', { defaultValue: '' });
  const [feedFilter, setFeedFilter] = useQueryState('acct_feed', { defaultValue: '' });
  const [dispFilter, setDispFilter] = useQueryState('acct_disp', { defaultValue: '' });
  const [sortKey, setSortKey] = useQueryState('sort', { defaultValue: 'id' });
  const [sortDir, setSortDir] = useQueryState('dir', { defaultValue: 'asc' });
  const [search, setSearch] = useQueryState('q', { defaultValue: '' });

  const accounts = useAccounts({
    entity: entityFilter || null,
    feed_status: feedFilter || null,
    disposition: dispFilter || null,
  });
  const entities = useEntities();
  const state = useAppState();
  const score = useScoreEstate();

  const sorting: SortingState = [{ id: sortKey, desc: sortDir === 'desc' }];
  const canScore = ['P2', 'P6'].includes(state.data?.persona.id ?? '');

  const columns = useMemo<ColumnDef<Account, unknown>[]>(
    () => [
      {
        id: 'id',
        header: 'Account',
        accessorFn: (row) => row.id,
        cell: (info) => (
          <span className="ident">{(info.row.original as Account).iban_masked}</span>
        ),
        size: 110,
      },
      {
        id: 'entity_id',
        header: 'Entity',
        accessorFn: (row) => row.entity_id,
        cell: (info) => (
          <button
            type="button"
            className="ident text-[var(--info-11)] hover:underline"
            onClick={(event) => {
              event.stopPropagation();
              onSelect((info.row.original as Account).entity_id);
            }}
          >
            {(info.row.original as Account).entity_id}
          </button>
        ),
        size: 110,
      },
      {
        id: 'bank_name',
        header: 'Bank',
        accessorFn: (row) => row.bank_name,
        cell: (info) => (
          <span className="truncate" translate="no">
            {(info.row.original as Account).bank_name}
          </span>
        ),
        size: 160,
      },
      {
        id: 'purpose',
        header: 'Purpose',
        accessorFn: (row) => row.purpose,
        cell: (info) => titleCase((info.row.original as Account).purpose),
        size: 110,
      },
      {
        id: 'currency',
        header: 'Ccy',
        accessorFn: (row) => row.currency,
        cell: (info) => (
          <span className="ident" translate="no">
            {(info.row.original as Account).currency}
          </span>
        ),
        size: 60,
      },
      {
        id: 'feed_status',
        header: 'Feed',
        accessorFn: (row) => row.feed_status,
        cell: (info) => {
          const account = info.row.original as Account;
          return account.feed_status === 'live' ? (
            <span className="flex items-center gap-1 text-[var(--text-tertiary)]">
              <Dot tone="ok" title="Feed current" />
              <span translate="no">{account.feed_type}</span>
            </span>
          ) : (
            <StaleBadge status={account.feed_status} />
          );
        },
        size: 110,
      },
      {
        id: 'balance',
        header: 'Balance',
        accessorFn: (row) => row.balance?.usd ?? 0,
        cell: (info) => {
          const account = info.row.original as Account;
          return account.balance ? <Figure value={account.balance} compact /> : '—';
        },
        meta: 'num',
        size: 120,
      },
      {
        id: 'score_total',
        header: 'Score',
        accessorFn: (row) => row.score_total ?? -1,
        cell: (info) => {
          const account = info.row.original as Account;
          if (account.score_total === null) return '—';
          return (
            <span
              className="tnum"
              title={`T1 panel ${account.score_panel}, T2 unique ${account.score_unique}, T3 activity ${account.score_active}, T4 legal ${account.score_legal}`}
            >
              {account.score_total}/4
            </span>
          );
        },
        meta: 'num',
        size: 70,
      },
      {
        id: 'disposition',
        header: 'Disposition',
        accessorFn: (row) => row.disposition ?? '',
        cell: (info) => {
          const value = (info.row.original as Account).disposition;
          if (!value) return '—';
          return (
            <Badge tone={value === 'keep' ? 'ok' : value === 'migrate' ? 'warn' : 'err'}>
              {titleCase(value)}
            </Badge>
          );
        },
        size: 100,
      },
      {
        id: 'last_movement',
        header: 'Last movement',
        accessorFn: (row) => row.last_movement ?? '',
        cell: (info) => {
          const value = (info.row.original as Account).last_movement;
          return <span className="tnum">{value ? date(value) : 'never'}</span>;
        },
        size: 120,
      },
      {
        id: 'annual_cost_usd',
        header: 'Annual cost',
        accessorFn: (row) => row.annual_cost_usd,
        cell: (info) => <UsdFigure usd={(info.row.original as Account).annual_cost_usd} />,
        meta: 'num',
        size: 110,
      },
    ],
    [onSelect],
  );

  const activeFilters = [
    entityFilter && `entity ${entityFilter}`,
    feedFilter && `feed ${feedFilter}`,
    dispFilter && `disposition ${dispFilter}`,
    search && `search “${search}”`,
  ].filter((value): value is string => Boolean(value));

  const clearFilters = () => {
    void setEntityFilter('');
    void setFeedFilter('');
    void setDispFilter('');
    void setSearch('');
  };

  const rows = accounts.data ?? [];
  const totalCost = rows.reduce((sum, row) => sum + row.annual_cost_usd, 0);

  return (
    <Panel
      title="Banking register"
      subtitle={
        accounts.isPending
          ? 'loading…'
          : `${rows.length} accounts · ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(totalCost)} annual cost`
      }
      actions={
        <Button
          variant="secondary"
          disabled={!canScore || score.isPending}
          title={
            canScore
              ? 'Run the four-test scorer across the estate'
              : 'Only the Group Treasurer and the Risk and Control Analyst may run the scorer'
          }
          onClick={() => score.mutate({ persist: true })}
        >
          <Calculator size={12} aria-hidden />
          {score.isPending ? 'Scoring…' : 'Run scorer'}
        </Button>
      }
      className="h-full"
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-subtle)] px-2 py-1.5">
        <div className="flex items-center gap-1.5">
          <Search size={12} className="text-[var(--text-tertiary)]" aria-hidden />
          <label htmlFor="account-search" className="sr-only">
            Search accounts
          </label>
          <input
            id="account-search"
            value={search}
            onChange={(event) => void setSearch(event.target.value)}
            placeholder="Filter by bank, purpose or entity…"
            className="h-6 w-[220px] rounded-[3px] bg-[var(--surface-1)] px-2 text-[11px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
          />
        </div>

        <label htmlFor="f-entity" className="sr-only">Entity</label>
        <select
          id="f-entity"
          value={entityFilter}
          onChange={(event) => void setEntityFilter(event.target.value)}
          className="h-6 rounded-[3px] px-1.5 text-[11px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
        >
          <option value="">All entities</option>
          {(entities.data ?? []).map((entity) => (
            <option key={entity.id} value={entity.id}>
              {entity.short_name}
            </option>
          ))}
        </select>

        <label htmlFor="f-feed" className="sr-only">Feed status</label>
        <select
          id="f-feed"
          value={feedFilter}
          onChange={(event) => void setFeedFilter(event.target.value)}
          className="h-6 rounded-[3px] px-1.5 text-[11px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
        >
          <option value="">All feeds</option>
          <option value="live">Live</option>
          <option value="stale">Stale</option>
          <option value="offline">Offline</option>
        </select>

        <label htmlFor="f-disp" className="sr-only">Disposition</label>
        <select
          id="f-disp"
          value={dispFilter}
          onChange={(event) => void setDispFilter(event.target.value)}
          className="h-6 rounded-[3px] px-1.5 text-[11px] shadow-[inset_0_0_0_1px_var(--border-interactive)]"
        >
          <option value="">All dispositions</option>
          <option value="keep">Keep</option>
          <option value="migrate">Migrate</option>
          <option value="close">Close</option>
        </select>

        {activeFilters.length ? (
          <Button variant="ghost" onClick={clearFilters}>
            Clear {activeFilters.length} filter{activeFilters.length > 1 ? 's' : ''}
          </Button>
        ) : null}

        {score.data ? (
          <span className="ml-auto text-[11px] text-[var(--text-tertiary)]">
            Scored {score.data.scored}, persisted {score.data.persisted}
          </span>
        ) : null}
      </div>

      {accounts.isPending ? (
        <SkeletonRows rows={14} cols={8} />
      ) : accounts.error ? (
        <ErrorState error={accounts.error} onRetry={() => accounts.refetch()} />
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          sorting={sorting}
          onSortingChange={(next) => {
            const first = next[0];
            void setSortKey(first?.id ?? 'id');
            void setSortDir(first?.desc ? 'desc' : 'asc');
          }}
          globalFilter={search}
          getRowId={(row) => row.id}
          dense
          height={460}
          emptyState={<FilteredEmpty filters={activeFilters} onClear={clearFilters} />}
        />
      )}
    </Panel>
  );
}

function BankPanel() {
  const banks = useBanks();
  if (banks.isPending) return <SkeletonRows rows={12} cols={6} />;
  if (banks.error) return <ErrorState error={banks.error} onRetry={() => banks.refetch()} />;

  return (
    <Panel title="Bank panel" subtitle={`${banks.data?.length ?? 0} relationships`}>
      <table className="grid-table">
        <thead>
          <tr>
            <th scope="col" className="freeze-col">Bank</th>
            <th scope="col">Tier</th>
            <th scope="col">BIC</th>
            <th scope="col">Connectivity</th>
            <th scope="col">Panel status</th>
            <th scope="col" className="num">Accounts</th>
            <th scope="col" className="num">Countries</th>
            <th scope="col" className="num">Cash limit</th>
            <th scope="col" className="num">Utilised</th>
          </tr>
        </thead>
        <tbody>
          {(banks.data ?? []).map((bank) => {
            const utilisation =
              bank.limit_usd && bank.utilised_usd ? bank.utilised_usd / bank.limit_usd : null;
            return (
              <tr key={bank.id}>
                <td className="freeze-col truncate" translate="no">{bank.name}</td>
                <td>{titleCase(bank.tier)}</td>
                <td className="ident" translate="no">{bank.swift_bic ?? '—'}</td>
                <td className="ident" translate="no">{bank.connectivity}</td>
                <td>
                  <Badge
                    tone={
                      bank.panel_status === 'panel'
                        ? 'ok'
                        : bank.panel_status === 'exit'
                          ? 'err'
                          : bank.panel_status === 'under_review'
                            ? 'warn'
                            : 'neutral'
                    }
                  >
                    {titleCase(bank.panel_status)}
                  </Badge>
                </td>
                <td className="num tnum">{bank.account_count}</td>
                <td className="num tnum">{bank.countries_served.length}</td>
                <td className="num tnum">
                  {bank.limit_usd !== null ? <UsdFigure usd={bank.limit_usd} compact /> : '—'}
                </td>
                <td className="num tnum">
                  {utilisation !== null ? (
                    <span
                      style={{
                        color:
                          utilisation > 0.85
                            ? 'var(--err-11)'
                            : utilisation > 0.6
                              ? 'var(--warn-11)'
                              : 'var(--text-primary)',
                      }}
                    >
                      {pct(utilisation, 0)}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}

function CoverageGrid() {
  const matrix = useCoverageMatrix();
  if (matrix.isPending) return <SkeletonRows rows={12} cols={10} />;
  if (matrix.error) return <ErrorState error={matrix.error} onRetry={() => matrix.refetch()} />;
  const data = matrix.data;
  if (!data) return null;

  return (
    <Panel
      title="Country by bank coverage"
      subtitle="the reference grid, used to decide who can serve where"
    >
      <table className="grid-table dense" style={{ tableLayout: 'fixed' }}>
        <thead>
          <tr>
            <th scope="col" className="freeze-col" style={{ width: 170 }}>Bank</th>
            {data.countries.map((country) => (
              <th key={country.iso2} scope="col" className="num" style={{ width: 46 }}>
                <abbr title={`${country.name} · Route ${country.route}`} className="no-underline">
                  {country.iso2}
                </abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.banks.map((bank) => (
            <tr key={bank.id}>
              <td className="freeze-col truncate" translate="no">
                <span className="flex items-center gap-1">
                  <Dot
                    tone={bank.panel_status === 'panel' ? 'ok' : bank.panel_status === 'exit' ? 'err' : 'neutral'}
                    title={titleCase(bank.panel_status)}
                  />
                  {bank.name}
                </span>
              </td>
              {data.countries.map((country) => {
                const serves = data.grid[bank.id]?.[country.iso2] ?? false;
                return (
                  <td
                    key={country.iso2}
                    className="num"
                    title={`${bank.name} ${serves ? 'serves' : 'does not serve'} ${country.name}`}
                  >
                    <span style={{ color: serves ? 'var(--ok-11)' : 'var(--text-disabled)' }}>
                      {serves ? '✓' : '·'}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Feeds() {
  const accounts = useAccounts();
  const [showAll, setShowAll] = useState(false);
  if (accounts.isPending) return <SkeletonRows rows={10} cols={5} />;

  const rows = accounts.data ?? [];
  const degraded = rows.filter((row) => row.feed_status !== 'live');
  const shown = showAll ? rows : degraded;

  return (
    <div className="space-y-2">
      <Panel title="Feed health" subtitle={`${degraded.length} of ${rows.length} degraded`}>
        <div className="grid grid-cols-4 gap-4 p-3">
          <Stat label="Accounts" value={rows.length} />
          <Stat label="Live" value={rows.filter((r) => r.feed_status === 'live').length} tone="ok" />
          <Stat label="Stale" value={rows.filter((r) => r.feed_status === 'stale').length} tone="warn" />
          <Stat
            label="Offline"
            value={rows.filter((r) => r.feed_status === 'offline').length}
            tone="err"
          />
        </div>
        <p className="border-t border-[var(--border-subtle)] px-3 py-2 text-[11px] text-[var(--text-tertiary)]">
          Staleness tracks connectivity, not diligence: a portal-only or unconnected bank means a
          balance someone keys in by hand. That is the integration cost the TMS decision turns on.
        </p>
      </Panel>

      <Panel
        title={showAll ? 'All feeds' : 'Degraded feeds'}
        actions={
          <Button variant="ghost" onClick={() => setShowAll((value) => !value)}>
            {showAll ? 'Show degraded only' : 'Show all'}
          </Button>
        }
      >
        <table className="grid-table dense">
          <thead>
            <tr>
              <th scope="col" className="freeze-col">Account</th>
              <th scope="col">Entity</th>
              <th scope="col">Bank</th>
              <th scope="col">Type</th>
              <th scope="col">Status</th>
              <th scope="col">Last movement</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((account) => (
              <tr key={account.id}>
                <td className="freeze-col ident">{account.iban_masked}</td>
                <td className="ident">{account.entity_id}</td>
                <td className="truncate" translate="no">{account.bank_name}</td>
                <td className="ident" translate="no">{account.feed_type}</td>
                <td>
                  {account.feed_status === 'live' ? (
                    <span className="flex items-center gap-1 text-[var(--text-tertiary)]">
                      <Dot tone="ok" title="Current" /> live
                    </span>
                  ) : (
                    <StaleBadge status={account.feed_status} />
                  )}
                </td>
                <td className="tnum">
                  {account.last_movement ? date(account.last_movement) : 'never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
