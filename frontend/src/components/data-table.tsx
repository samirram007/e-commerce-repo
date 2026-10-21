import type { ReactNode } from "react";
import type { ListStateApi } from "../hooks/use-list-state";
import { cn } from "../lib/utils";
import {
  EmptyState,
  ErrorState,
  Field,
  Input,
  TablePagination,
  TABLE_PAGE_SIZE_OPTIONS,
  type Column,
  Spinner,
} from "./ui";

/** A table column; `sortKey` enables server-side sorting on that column. */
export interface ServerColumn<T> extends Column<T> {
  /** Model attribute the backend allowlists for sorting. Omit for static columns. */
  sortKey?: string;
}

export interface ServerDataTableProps<T> {
  columns: ServerColumn<T>[];
  rows: T[] | undefined;
  rowKey: (row: T, index: number) => string;
  /** Server-side list state + params from `useListState`. */
  list: ListStateApi;
  total?: number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: ReactNode;
  searchPlaceholder?: string;
  /** Extra filter controls rendered next to the search box. */
  filters?: ReactNode;
  /** Primary/secondary actions rendered on the right of the toolbar. */
  actions?: ReactNode;
  /** Hide the built-in search input (still available via list.setSearch). */
  hideSearch?: boolean;
  pageSizeOptions?: number[];
}

/**
 * Global CRUD DataTable: server-side search (debounced), sort, filters and
 * pagination, driven by a `useListState` instance so every screen shares the
 * same query contract ({page, page_size, search, sort, order, ...filters}).
 */
export function ServerDataTable<T>({
  columns,
  rows,
  rowKey,
  list,
  total,
  loading,
  error,
  onRetry,
  empty,
  searchPlaceholder = "Search…",
  filters,
  actions,
  hideSearch,
  pageSizeOptions = TABLE_PAGE_SIZE_OPTIONS,
}: ServerDataTableProps<T>) {
  const { state, setPage, setPageSize } = list;
  const pageCount = Math.max(1, Math.ceil((total ?? rows?.length ?? 0) / state.pageSize));
  const from = total === 0 || !rows?.length ? 0 : (state.page - 1) * state.pageSize + 1;
  const to = total === undefined ? (rows?.length ?? 0) : Math.min(state.page * state.pageSize, total);

  return (
    <>
      <div className="toolbar" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <div className="toolbar" style={{ flex: 1 }}>
          {hideSearch ? null : (
            <Field>
              <Input
                value={list.searchInput}
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                onChange={(event) => list.setSearch(event.target.value)}
              />
            </Field>
          )}
          {filters}
        </div>
        {actions ? <div className="toolbar">{actions}</div> : null}
      </div>

      {loading ? <Spinner /> : null}
      {!loading && error ? <ErrorState error={error} onRetry={onRetry} /> : null}
      {!loading && !error && (!rows || rows.length === 0) ? (
        (empty ?? <EmptyState />)
      ) : null}
      {!loading && !error && rows && rows.length > 0 ? (
        <table className="data">
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  style={column.align ? { textAlign: column.align } : undefined}
                  aria-sort={
                    column.sortKey && state.sort === column.sortKey
                      ? state.order === "asc"
                        ? "ascending"
                        : "descending"
                      : undefined
                  }
                >
                  {column.sortKey ? (
                    <button
                      type="button"
                      className={cn("th-sort", state.sort === column.sortKey && "active")}
                      onClick={() => list.toggleSort(column.sortKey as string)}
                    >
                      {column.header}
                      <span className="sort-ind" aria-hidden="true">
                        {state.sort === column.sortKey ? (state.order === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={rowKey(row, index)}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={column.className}
                    style={column.align ? { textAlign: column.align } : undefined}
                  >
                    {column.render ? column.render(row, index) : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <TablePagination
        from={from}
        to={to}
        total={total}
        page={state.page}
        pageCount={pageCount}
        pageSize={state.pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        pageSizeOptions={pageSizeOptions}
      />
    </>
  );
}
