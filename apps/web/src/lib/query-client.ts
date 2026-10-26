import { QueryClient } from "@tanstack/react-query";

// Shared defaults: modest stale time, no auto-refetch-on-focus spam,
// bounded retries. Mutation-heavy ERP data — invalidation is explicit.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: 0 },
  },
});

/** Hard cache eviction on user/tenant switch or logout (never leak cross-company data). */
export function clearSensitiveCaches(): void {
  queryClient.clear();
}
