import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addCountLine,
  adjustStock,
  createCount,
  fetchCount,
  fetchLedger,
  fetchLocationOptions,
  fetchOnHand,
  fetchProductOptions,
  fetchReconcile,
  fetchValuation,
  postCount,
  transferStock,
  type LedgerFilters,
  type OnHandFilters,
} from "./api";
import type { AdjustmentPayload, TransferPayload } from "./schemas";

export const inventoryKeys = {
  all: ["inventory"] as const,
  onHand: (filters: OnHandFilters) => [...inventoryKeys.all, "on-hand", filters] as const,
  ledger: (filters: LedgerFilters) => [...inventoryKeys.all, "ledger", filters] as const,
  valuation: () => [...inventoryKeys.all, "valuation"] as const,
  reconcile: () => [...inventoryKeys.all, "reconcile"] as const,
  count: (id: string) => [...inventoryKeys.all, "count", id] as const,
  productOptions: () => ["catalog", "products", "options"] as const,
  locationOptions: () => ["storage", "locations", "options"] as const,
};

export function onHandQueryOptions(filters: OnHandFilters = {}) {
  return queryOptions({
    queryKey: inventoryKeys.onHand(filters),
    queryFn: () => fetchOnHand(filters),
  });
}

export function ledgerQueryOptions(filters: LedgerFilters = {}) {
  return queryOptions({
    queryKey: inventoryKeys.ledger(filters),
    queryFn: () => fetchLedger(filters),
  });
}

export function valuationQueryOptions() {
  return queryOptions({
    queryKey: inventoryKeys.valuation(),
    queryFn: fetchValuation,
  });
}

export function reconcileQueryOptions() {
  return queryOptions({
    queryKey: inventoryKeys.reconcile(),
    queryFn: fetchReconcile,
  });
}

export function countQueryOptions(id: string) {
  return queryOptions({
    queryKey: inventoryKeys.count(id),
    queryFn: () => fetchCount(id),
    enabled: id.length > 0,
  });
}

export function productOptionsQueryOptions() {
  return queryOptions({
    queryKey: inventoryKeys.productOptions(),
    queryFn: fetchProductOptions,
    staleTime: 5 * 60_000,
  });
}

export function locationOptionsQueryOptions() {
  return queryOptions({
    queryKey: inventoryKeys.locationOptions(),
    queryFn: fetchLocationOptions,
    staleTime: 5 * 60_000,
  });
}

function invalidateStock(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
}

export function useTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TransferPayload) => transferStock(input),
    onSuccess: () => invalidateStock(queryClient),
  });
}

export function useAdjustment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AdjustmentPayload) => adjustStock(input),
    onSuccess: () => invalidateStock(queryClient),
  });
}

export function useCreateCount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (locationId: string) => createCount(locationId),
    onSuccess: () => invalidateStock(queryClient),
  });
}

export function useAddCountLine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, productId, countedQty }: { id: string; productId: string; countedQty: string }) =>
      addCountLine(id, { product_id: productId, counted_qty: countedQty }),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: inventoryKeys.count(variables.id) }),
  });
}

export function usePostCount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => postCount(id),
    onSuccess: () => invalidateStock(queryClient),
  });
}
