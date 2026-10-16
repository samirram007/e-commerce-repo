import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createShipment,
  dispatchShipment,
  fetchShipment,
  fetchShipments,
  transitionShipment,
} from "./api";

export interface ShipmentFilters {
  status?: string;
  orderId?: string;
}

export const shipmentKeys = {
  all: ["shipments"] as const,
  list: (filters: ShipmentFilters) => [...shipmentKeys.all, "list", filters] as const,
  detail: (id: string) => [...shipmentKeys.all, "detail", id] as const,
};

export function shipmentsQueryOptions(filters: ShipmentFilters = {}) {
  return queryOptions({
    queryKey: shipmentKeys.list(filters),
    queryFn: () => fetchShipments(filters),
  });
}

export function shipmentQueryOptions(id: string, enabled = true) {
  return queryOptions({
    queryKey: shipmentKeys.detail(id),
    queryFn: () => fetchShipment(id),
    enabled: enabled && Boolean(id),
  });
}

export function useCreateShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => createShipment(orderId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: shipmentKeys.all }),
  });
}

export function useTransitionShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, toStatus }: { id: string; toStatus: string }) =>
      transitionShipment(id, toStatus),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: shipmentKeys.all }),
  });
}

export function useDispatchShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, carrier }: { id: string; carrier: string }) => dispatchShipment(id, carrier),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: shipmentKeys.all }),
  });
}
