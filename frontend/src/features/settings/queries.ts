import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  closeAccountingPeriod,
  closeFiscalYear,
  createCompany,
  createFiscalYear,
  createStorageLocation,
  createTaxRate,
  fetchCompanies,
  fetchFiscalYearPeriods,
  fetchFiscalYears,
  fetchStorageLocations,
  fetchTaxRates,
  forwardFiscalYear,
  postOpeningBalances,
  updateCompany,
  updateCompanyAddresses,
  fetchCompanyAddresses,
} from "./api";
import type {
  CompanyCreatePayload,
  CompanyUpdatePayload,
  FiscalYearPayload,
  OpeningBalancesPayload,
  StorageLocationPayload,
  TaxRatePayload,
  CompanyAddressIn,
} from "./schemas";

export const settingsKeys = {
  all: ["settings"] as const,
  companies: () => [...settingsKeys.all, "companies"] as const,
  taxRates: () => [...settingsKeys.all, "tax-rates"] as const,
  locations: () => [...settingsKeys.all, "storage-locations"] as const,
  fiscalYears: () => [...settingsKeys.all, "fiscal-years"] as const,
  fiscalYearPeriods: (fiscalYearId: string) =>
    [...settingsKeys.all, "fiscal-year-periods", fiscalYearId] as const,
};

/** Lifecycle mutations refresh the year list, its periods, and the period
 * context (the topbar fiscal-year picker shows open/closed state). */
function invalidateFiscal(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: settingsKeys.fiscalYears() });
  void queryClient.invalidateQueries({ queryKey: [...settingsKeys.all, "fiscal-year-periods"] });
  void queryClient.invalidateQueries({ queryKey: ["periods"] });
  void queryClient.invalidateQueries({ queryKey: ["accounting"] });
}

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

export function fiscalYearPeriodsQueryOptions(fiscalYearId: string) {
  return queryOptions({
    queryKey: settingsKeys.fiscalYearPeriods(fiscalYearId),
    queryFn: () => fetchFiscalYearPeriods(fiscalYearId),
    enabled: Boolean(fiscalYearId),
  });
}

export function useClosePeriod(fiscalYearId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (periodId: string) => closeAccountingPeriod(fiscalYearId, periodId),
    onSuccess: () => invalidateFiscal(queryClient),
  });
}

export function useCloseFiscalYear() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fiscalYearId: string) => closeFiscalYear(fiscalYearId),
    onSuccess: () => invalidateFiscal(queryClient),
  });
}

export function useForwardFiscalYear() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fiscalYearId: string) => forwardFiscalYear(fiscalYearId),
    onSuccess: () => invalidateFiscal(queryClient),
  });
}

export function usePostOpeningBalances() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fiscalYearId, input }: { fiscalYearId: string; input: OpeningBalancesPayload }) =>
      postOpeningBalances(fiscalYearId, input),
    onSuccess: () => invalidateFiscal(queryClient),
  });
}

// @ts-ignore TS6133 - queryClient is used via invalidateQueries method
export function useManageCompanyAddresses() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { company_id: string; addresses: CompanyAddressIn[] }) =>
      updateCompanyAddresses(input.company_id, input.addresses),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.companies() }),
  });
}

export function useCompanyAddresses(companyId: string) {
  // @ts-ignore TS6133 - queryClient is used via invalidateQueries method
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["company-addresses", companyId],
    queryFn: () => fetchCompanyAddresses(companyId),
    enabled: Boolean(companyId),
  });
}
