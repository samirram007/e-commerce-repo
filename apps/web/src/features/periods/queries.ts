import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createReportingPeriod,
  deleteReportingPeriod,
  fetchAccountingPeriodOptions,
  fetchFiscalYearOptions,
  fetchPeriodContext,
  fetchReportingPeriods,
  setPeriodContext,
  updateReportingPeriod,
} from "./api";
import type { PeriodContextPayload, ReportingPeriodPayload } from "./schemas";

export const periodsKeys = {
  all: ["periods"] as const,
  context: () => [...periodsKeys.all, "context"] as const,
  fiscalYears: () => [...periodsKeys.all, "fiscal-years"] as const,
  accountingPeriods: (fiscalYearId: string) =>
    [...periodsKeys.all, "accounting-periods", fiscalYearId] as const,
  reportingPeriods: () => [...periodsKeys.all, "reporting-periods"] as const,
};

export function periodContextQueryOptions() {
  return queryOptions({
    queryKey: periodsKeys.context(),
    queryFn: fetchPeriodContext,
    staleTime: 60_000,
  });
}

export function fiscalYearOptionsQueryOptions() {
  return queryOptions({
    queryKey: periodsKeys.fiscalYears(),
    queryFn: fetchFiscalYearOptions,
    staleTime: 5 * 60_000,
  });
}

export function accountingPeriodOptionsQueryOptions(fiscalYearId: string | null) {
  return queryOptions({
    queryKey: periodsKeys.accountingPeriods(fiscalYearId ?? ""),
    queryFn: () => fetchAccountingPeriodOptions(fiscalYearId as string),
    enabled: Boolean(fiscalYearId),
  });
}

export function reportingPeriodsQueryOptions() {
  return queryOptions({
    queryKey: periodsKeys.reportingPeriods(),
    queryFn: fetchReportingPeriods,
  });
}

/**
 * Persist the signed-in user's period selection. The payload replaces the whole
 * context, so switching fiscal year clears any accounting/reporting sub-period.
 */
export function useSetPeriodContext() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PeriodContextPayload) => setPeriodContext(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: periodsKeys.all });
    },
  });
}

export function useCreateReportingPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ReportingPeriodPayload) => createReportingPeriod(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: periodsKeys.reportingPeriods() });
      void queryClient.invalidateQueries({ queryKey: periodsKeys.context() });
    },
  });
}

export function useUpdateReportingPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ReportingPeriodPayload }) =>
      updateReportingPeriod(id, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: periodsKeys.reportingPeriods() });
      void queryClient.invalidateQueries({ queryKey: periodsKeys.context() });
    },
  });
}

export function useDeleteReportingPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteReportingPeriod(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: periodsKeys.reportingPeriods() });
      void queryClient.invalidateQueries({ queryKey: periodsKeys.context() });
    },
  });
}
