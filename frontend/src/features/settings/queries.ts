import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCompany,
  createFiscalYear,
  createStorageLocation,
  createTaxRate,
  fetchCompanies,
  fetchFiscalYears,
  fetchStorageLocations,
  fetchTaxRates,
  updateCompany,
} from "./api";
import type {
  CompanyCreatePayload,
  CompanyUpdatePayload,
  FiscalYearPayload,
  StorageLocationPayload,
  TaxRatePayload,
} from "./schemas";

export const settingsKeys = {
  all: ["settings"] as const,
  companies: () => [...settingsKeys.all, "companies"] as const,
  taxRates: () => [...settingsKeys.all, "tax-rates"] as const,
  locations: () => [...settingsKeys.all, "storage-locations"] as const,
  fiscalYears: () => [...settingsKeys.all, "fiscal-years"] as const,
};

export function companiesQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.companies(),
    queryFn: fetchCompanies,
  });
}

export function taxRatesQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.taxRates(),
    queryFn: fetchTaxRates,
  });
}

export function storageLocationsQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.locations(),
    queryFn: fetchStorageLocations,
  });
}

export function fiscalYearsQueryOptions() {
  return queryOptions({
    queryKey: settingsKeys.fiscalYears(),
    queryFn: fetchFiscalYears,
  });
}

export function useCreateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CompanyCreatePayload) => createCompany(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.companies() }),
  });
}

export function useUpdateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: CompanyUpdatePayload }) =>
      updateCompany(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.companies() }),
  });
}

export function useCreateTaxRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TaxRatePayload) => createTaxRate(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.taxRates() }),
  });
}

export function useCreateStorageLocation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StorageLocationPayload) => createStorageLocation(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.locations() }),
  });
}

export function useCreateFiscalYear() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: FiscalYearPayload) => createFiscalYear(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.fiscalYears() }),
  });
}
