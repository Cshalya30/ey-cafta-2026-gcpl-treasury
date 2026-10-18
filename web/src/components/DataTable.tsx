/**
 * A dense, virtualized, URL-stateful table.
 *
 * Designed against the four NN/g data-table tasks: finding, comparing, viewing
 * one row, and acting. The identifier column and the header row both freeze,
 * sort state lives in the URL, and a selected row opens a non-modal side panel
 * rather than a modal, because a modal hides the records being compared against.
 */

import { useMemo, type ReactNode } from 'react';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { VList } from 'virtua';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cn } from './primitives';

export type DataTableProps<T> = {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  globalFilter?: string;
  onRowClick?: (row: T) => void;
  selectedId?: string | null;
  getRowId: (row: T) => string;
  dense?: boolean;
  /** Any list over 50 rows virtualizes. */
  virtualizeFrom?: number;
  emptyState?: ReactNode;
  height?: number;
};

export function DataTable<T>({
  data,
  columns,
  sorting,
  onSortingChange,
  globalFilter,
  onRowClick,
  selectedId,
  getRowId,
  dense = false,
  virtualizeFrom = 50,
  emptyState,
  height = 520,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter: globalFilter ?? '' },
    onSortingChange: (updater) =>
      onSortingChange(typeof updater === 'function' ? updater(sorting) : updater),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getRowId: (row) => getRowId(row),
  });

  const rows = table.getRowModel().rows;
  const rowHeight = dense ? 24 : 32;
  const virtualize = rows.length > virtualizeFrom;

  const header = useMemo(
    () => (
      <thead>
        {table.getHeaderGroups().map((group) => (
          <tr key={group.id}>
            {group.headers.map((head, index) => {
              const sorted = head.column.getIsSorted();
              const sortable = head.column.getCanSort();
              return (
                <th
                  key={head.id}
                  scope="col"
                  aria-sort={
                    sorted === 'asc'
                      ? 'ascending'
                      : sorted === 'desc'
                        ? 'descending'
                        : undefined
                  }
                  style={{ width: head.getSize() ? `${head.getSize()}px` : undefined }}
                  className={cn(index === 0 && 'freeze-col')}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={head.column.getToggleSortingHandler()}
                      className="flex h-full w-full items-center gap-1 text-left hover:text-[var(--text-primary)]"
                    >
                      {flexRender(head.column.columnDef.header, head.getContext())}
                      <span className="sort-icon" aria-hidden>
                        {sorted === 'asc' ? (
                          <ArrowUp size={11} />
                        ) : sorted === 'desc' ? (
                          <ArrowDown size={11} />
                        ) : (
                          <ChevronsUpDown size={11} />
                        )}
                      </span>
                    </button>
                  ) : (
                    flexRender(head.column.columnDef.header, head.getContext())
                  )}
                </th>
              );
            })}
          </tr>
        ))}
      </thead>
    ),
    [table, sorting],
  );

  if (rows.length === 0 && emptyState) return <>{emptyState}</>;

  const renderRow = (rowIndex: number) => {
    const row = rows[rowIndex];
    if (!row) return null;
    const id = getRowId(row.original);
    return (
      <tr
        key={row.id}
        aria-selected={selectedId === id}
        tabIndex={onRowClick ? 0 : undefined}
        onClick={onRowClick ? () => onRowClick(row.original) : undefined}
        onKeyDown={
          onRowClick
            ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onRowClick(row.original);
                }
              }
            : undefined
        }
        className={cn(onRowClick && 'cursor-pointer')}
      >
        {row.getVisibleCells().map((cell, index) => (
          <td
            key={cell.id}
            className={cn(index === 0 && 'freeze-col', cell.column.columnDef.meta ? 'num' : '')}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </tr>
    );
  };

  if (!virtualize) {
    return (
      <table className={cn('grid-table', dense && 'dense')}>
        {header}
        <tbody>{rows.map((_, index) => renderRow(index))}</tbody>
      </table>
    );
  }

  return (
    <div className="flex min-h-0 flex-col">
      <table className={cn('grid-table', dense && 'dense')} style={{ tableLayout: 'fixed' }}>
        {header}
      </table>
      <VList style={{ height }} count={rows.length} overscan={6}>
        {(index) => (
          <table
            className={cn('grid-table', dense && 'dense')}
            style={{ tableLayout: 'fixed', height: rowHeight }}
          >
            <tbody>{renderRow(index)}</tbody>
          </table>
        )}
      </VList>
      <p className="border-t border-[var(--border-subtle)] px-3 py-1 text-[11px] text-[var(--text-tertiary)]">
        {rows.length} rows, virtualized. Scroll to load more into the DOM.
      </p>
    </div>
  );
}
