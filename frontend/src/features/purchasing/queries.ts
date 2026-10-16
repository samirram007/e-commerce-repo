import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAdhocBill,
  createBillFromReceipt,
  createPurchaseOrder,
  fetchLocationOptions,
  fetchProductOptions,
  fetchPurchaseOrderLines,
  fetchPurchaseOrders,
  fetchVendorBills,
  fetchVendorBillLines,
  fetchVendors,
  receiveGoods,
  transitionPurchaseOrder,
  type PoAction,
} from "./api";
import type {
  AdhocBillPayload,
  BillFromReceiptFormInput,
  PurchaseOrderPayload,
  ReceiveLinePayload,
} from "./schemas";

export const purchasingKeys = {
  all: ["purchasing"] as const,
  orders: (status?: string) => [...purchasingKeys.all, "orders", status ?? "all"] as const,
  orderLines: (id: string) => [...purchasingKeys.all, "order", id, "lines"] as const,
  bills: () => [...purchasingKeys.all, "bills"] as const,
  billLines: (id: string) => [...purchasingKeys.all, "bill", id, "lines"] as const,
  vendors: () => ["partners", "vendors"] as const,
  productOptions: () => ["catalog", "products", "options"] as const,
  locationOptions: () => ["storage", "locations", "options"] as const,
};

export function purchaseOrdersQueryOptions(status?: string) {
  return queryOptions({
    queryKey: purchasingKeys.orders(status),
    queryFn: () => fetchPurchaseOrders(status),
  });
}

export function purchaseOrderLinesQueryOptions(id: string) {
  return queryOptions({
    queryKey: purchasingKeys.orderLines(id),
    queryFn: () => fetchPurchaseOrderLines(id),
    enabled: id.length > 0,
  });
}

export function vendorBillsQueryOptions() {
  return queryOptions({
    queryKey: purchasingKeys.bills(),
    queryFn: fetchVendorBills,
  });
}

export function vendorBillLinesQueryOptions(id: string) {
  return queryOptions({
    queryKey: purchasingKeys.billLines(id),
    queryFn: () => fetchVendorBillLines(id),
    enabled: id.length > 0,
  });
}

export function vendorsQueryOptions() {
  return queryOptions({
    queryKey: purchasingKeys.vendors(),
    queryFn: fetchVendors,
    staleTime: 5 * 60_000,
  });
}

export function productOptionsQueryOptions() {
  return queryOptions({
    queryKey: purchasingKeys.productOptions(),
    queryFn: fetchProductOptions,
    staleTime: 5 * 60_000,
  });
}

export function locationOptionsQueryOptions() {
  return queryOptions({
    queryKey: purchasingKeys.locationOptions(),
    queryFn: fetchLocationOptions,
    staleTime: 5 * 60_000,
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PurchaseOrderPayload) => createPurchaseOrder(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchasingKeys.all }),
  });
}

export function usePurchaseOrderAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: PoAction }) =>
      transitionPurchaseOrder(id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchasingKeys.all }),
  });
}

export function useReceiveGoods() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, lines }: { id: string; lines: ReceiveLinePayload[] }) =>
      receiveGoods(id, lines),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchasingKeys.all }),
  });
}

export function useCreateBillFromReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: BillFromReceiptFormInput) => createBillFromReceipt(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchasingKeys.bills() }),
  });
}

export function useCreateAdhocBill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AdhocBillPayload) => createAdhocBill(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchasingKeys.bills() }),
  });
}
