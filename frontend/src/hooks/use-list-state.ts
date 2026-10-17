import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/** Server-side list query contract shared by every CRUD screen. */
export interface ListState {
  page: number;
  pageSize: number;
  search: string;
  sort: string | null;
  order: "asc" | "desc";
  filters: Record<string, string>;
}

export const DEFAULT_PAGE_SIZE = 25;

export function initialListState(options?: {
  pageSize?: number;
  sort?: string | null;
  order?: "asc" | "desc";
}): ListState {
  return {
    page: 1,
    pageSize: options?.pageSize ?? DEFAULT_PAGE_SIZE,
    search: "",
    sort: options?.sort ?? null,
    order: options?.order ?? "asc",
    filters: {},
  };
}

/**
 * Map list state to backend query params (`app.shared.pagination.ListParams`).
 * Empty values are omitted so URLs stay clean and cache keys stay stable.
 */
export function toListParams(state: ListState): Record<string, string | number> {
  const params: Record<string, string | number> = {
    page: state.page,
    page_size: state.pageSize,
  };
  if (state.search.trim()) params.search = state.search.trim();
  if (state.sort) {
    params.sort = state.sort;
    params.order = state.order;
  }
  for (const [key, value] of Object.entries(state.filters)) {
    if (value !== "" && value !== undefined && value !== null) params[key] = value;
  }
  return params;
}

/** Cache key fragment for TanStack Query keys; stable for equal states. */
export function listQueryKey(state: ListState): (string | number)[] {
  return Object.entries(toListParams(state)).flat();
}

/** Click handler for sortable headers: same column flips direction, new column starts asc. */
export function toggleSort(state: ListState, column: string): Pick<ListState, "sort" | "order" | "page"> {
  if (state.sort !== column) return { sort: column, order: "asc", page: 1 };
  if (state.order === "asc") return { sort: column, order: "desc", page: 1 };
  return { sort: null, order: "asc", page: 1 };
}

export interface ListStateApi {
  state: ListState;
  params: Record<string, string | number>;
  searchInput: string;
  /** Update the debounced free-text search; resets to page 1. */
  setSearch: (value: string) => void;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  toggleSort: (column: string) => void;
  /** Set (or clear with "") a named server-side filter; resets to page 1. */
  setFilter: (key: string, value: string) => void;
  reset: () => void;
}

/**
 * Server-side list state: pagination, sort, filters and a debounced search.
 *
 * Every change (except page flips) resets to page 1 so the user never lands on
 * an empty page after filtering. The debounced `search` value is what feeds
 * `state`/`params`/the query key, so each keystroke does not fire a request.
 */
export function useListState(options?: {
  pageSize?: number;
  sort?: string | null;
  order?: "asc" | "desc";
  searchDebounceMs?: number;
  onStateChange?: (state: ListState) => void;
}): ListStateApi {
  const [state, setState] = useState<ListState>(() => initialListState(options));
  const [searchInput, setSearchInput] = useState("");
  const debounceRef = useRef<number>(-1);

  const emit = useCallback(
    (next: ListState) => {
      options?.onStateChange?.(next);
      return next;
    },
    [options],
  );

  const setSearch = useCallback(
    (value: string) => {
      setSearchInput(value);
      // debounced commit into server-driven state
      window.clearTimeout(debounceRef.current);
      debounceRef.current = window.setTimeout(() => {
        setState((prev) => {
          if (prev.search === value) return prev;
          return emit({ ...prev, search: value, page: 1 });
        });
      }, options?.searchDebounceMs ?? 300);
    },
    [emit, options],
  );

  // clear any pending search timer on unmount
  useEffect(() => () => window.clearTimeout(debounceRef.current), []);

  const setPage = useCallback((page: number) => {
    setState((prev) => (prev.page === page ? prev : { ...prev, page }));
  }, []);

  const setPageSize = useCallback(
    (pageSize: number) => {
      setState((prev) => emit({ ...prev, pageSize, page: 1 }));
    },
    [emit],
  );

  const applySort = useCallback(
    (column: string) => {
      setState((prev) => emit({ ...prev, ...toggleSort(prev, column) }));
    },
    [emit],
  );

  const setFilter = useCallback(
    (key: string, value: string) => {
      setState((prev) => {
        const filters = { ...prev.filters, [key]: value };
        return emit({ ...prev, filters, page: 1 });
      });
    },
    [emit],
  );

  const reset = useCallback(() => {
    setSearchInput("");
    setState((prev) => emit({ ...initialListState(options), filters: prev.filters }));
  }, [emit, options]);

  const params = useMemo(() => toListParams(state), [state]);

  return { state, params, searchInput, setSearch, setPage, setPageSize, toggleSort: applySort, setFilter, reset };
}
