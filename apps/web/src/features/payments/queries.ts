import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPayment,
  fetchAllocations,
  fetchCustomers,
  fetchPayments,
  fetchVendors,
} from "./api";
import type { PaymentCreateInput } from "./schemas";

export const paymentsKeys = {
  all: ["payments"] as const,
  list: () => [...paymentsKeys.all, "list"] as const,
  allocations: (paymentId: string) => [...paymentsKeys.all, "allocations", paymentId] as const,
  customers: () => [...paymentsKeys.all, "customers"] as const,
  vendors: () => [...paymentsKeys.all, "vendors"] as const,
};

export function paymentsQueryOptions() {
  return queryOptions({
    queryKey: paymentsKeys.list(),
    queryFn: fetchPayments,
  });
}

export function paymentAllocationsQueryOptions(paymentId: string) {
  return queryOptions({
    queryKey: paymentsKeys.allocations(paymentId),
    queryFn: () => fetchAllocations(paymentId),
    enabled: Boolean(paymentId),
  });
}

export function paymentCustomersQueryOptions() {
  return queryOptions({
    queryKey: paymentsKeys.customers(),
    queryFn: fetchCustomers,
    staleTime: 5 * 60_000,
  });
}

export function paymentVendorsQueryOptions() {
  return queryOptions({
    queryKey: paymentsKeys.vendors(),
    queryFn: fetchVendors,
    staleTime: 5 * 60_000,
  });
}

export function useCreatePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PaymentCreateInput) => createPayment(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentsKeys.all }),
  });
}
