import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteGateway, fetchGateways, saveGateway } from "./gateway-api";
import type { GatewayPayload } from "./gateway-schemas";

export const gatewayKeys = {
  all: ["payment-gateways"] as const,
  list: () => [...gatewayKeys.all, "list"] as const,
};

export function gatewaysQueryOptions() {
  return queryOptions({ queryKey: gatewayKeys.list(), queryFn: fetchGateways });
}

export function useSaveGateway() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, input }: { provider: string; input: GatewayPayload }) =>
      saveGateway(provider, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: gatewayKeys.all }),
  });
}

export function useDeleteGateway() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) => deleteGateway(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: gatewayKeys.all }),
  });
}
