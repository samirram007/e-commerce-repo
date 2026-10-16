import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  approveReturn,
  completeReturn,
  createReturn,
  fetchReturn,
  fetchReturns,
  rejectReturn,
} from "./api";
import type { ReturnCreatePayload } from "./schemas";

export const returnKeys = {
  all: ["returns"] as const,
  list: (status: string) => [...returnKeys.all, "list", status] as const,
  detail: (id: string) => [...returnKeys.all, "detail", id] as const,
};

export function returnsQueryOptions(status = "") {
  return queryOptions({
    queryKey: returnKeys.list(status),
    queryFn: () => fetchReturns(status),
  });
}

export function returnQueryOptions(id: string, enabled = true) {
  return queryOptions({
    queryKey: returnKeys.detail(id),
    queryFn: () => fetchReturn(id),
    enabled: enabled && Boolean(id),
  });
}

export function useCreateReturn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReturnCreatePayload) => createReturn(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: returnKeys.all }),
  });
}

export function useApproveReturn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => approveReturn(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: returnKeys.all }),
  });
}

export function useRejectReturn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => rejectReturn(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: returnKeys.all }),
  });
}

export function useCompleteReturn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => completeReturn(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: returnKeys.all }),
  });
}
