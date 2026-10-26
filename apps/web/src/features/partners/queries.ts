import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAddress,
  createCustomer,
  createVendor,
  fetchAddresses,
  fetchCustomers,
  fetchVendors,
  updateCustomer,
  updateVendor,
} from "./api";
import type { AddressPayload, PartnerCreatePayload, PartnerUpdatePayload } from "./schemas";

export const partnerKeys = {
  all: ["partners"] as const,
  customers: (search: string) => [...partnerKeys.all, "customers", search] as const,
  vendors: (search: string) => [...partnerKeys.all, "vendors", search] as const,
  addresses: (partnerType: string, partnerId: string) =>
    [...partnerKeys.all, "addresses", partnerType, partnerId] as const,
};

export function customersQueryOptions(search = "") {
  return queryOptions({
    queryKey: partnerKeys.customers(search),
    queryFn: () => fetchCustomers(search),
  });
}

export function vendorsQueryOptions(search = "") {
  return queryOptions({
    queryKey: partnerKeys.vendors(search),
    queryFn: () => fetchVendors(search),
  });
}

export function addressesQueryOptions(partnerType: string, partnerId: string) {
  return queryOptions({
    queryKey: partnerKeys.addresses(partnerType, partnerId),
    queryFn: () => fetchAddresses(partnerType, partnerId),
    enabled: Boolean(partnerType) && Boolean(partnerId),
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PartnerCreatePayload) => createCustomer(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: PartnerUpdatePayload }) =>
      updateCustomer(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
  });
}

export function useCreateVendor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PartnerCreatePayload) => createVendor(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
  });
}

export function useUpdateVendor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: PartnerUpdatePayload }) =>
      updateVendor(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
  });
}

export function useCreateAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      partnerType,
      partnerId,
      input,
    }: {
      partnerType: string;
      partnerId: string;
      input: AddressPayload;
    }) => createAddress(partnerType, partnerId, input),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({
        queryKey: partnerKeys.addresses(variables.partnerType, variables.partnerId),
      }),
  });
}
