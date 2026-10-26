import { useQuery } from "@tanstack/react-query";
import type { FiscalYearOption, PeriodContext } from "./schemas";
import {
  fiscalYearOptionsQueryOptions,
  periodContextQueryOptions,
  useSetPeriodContext,
} from "./queries";

/** Sentinel option value meaning "no fiscal year filter" (whole history). */
export const ALL_PERIODS = "";

export interface PeriodContextValue {
  /** The resolved server context (levels + effective date window). */
  context: PeriodContext | null;
  /** Active fiscal year, or `null` when the user chose "all periods". */
  fiscalYear: FiscalYearOption | null;
  /** Fiscal years the user may switch to (company-scoped, any member). */
  fiscalYears: FiscalYearOption[];
  /** Inclusive resolved window (`YYYY-MM-DD`), or `null` for unbounded. */
  effectiveFrom: string | null;
  effectiveTo: string | null;
  isLoading: boolean;
  isError: boolean;
  /** A fiscal-year switch is in flight. */
  isSwitching: boolean;
  /** Persist the active fiscal year; pass {@link ALL_PERIODS} to clear it. */
  setFiscalYear: (fiscalYearId: string) => void;
}

/**
 * User-wise period context. Every read-only screen may call this to scope its
 * data to the user's selected fiscal year; the selection is persisted per user
 * (per company) by the backend, so it survives reloads and sessions.
 */
export function usePeriodContext(): PeriodContextValue {
  const contextQuery = useQuery(periodContextQueryOptions());
  const fiscalYearsQuery = useQuery(fiscalYearOptionsQueryOptions());
  const mutation = useSetPeriodContext();

  const context = contextQuery.data ?? null;

  return {
    context,
    fiscalYear: context?.fiscal_year ?? null,
    fiscalYears: fiscalYearsQuery.data ?? [],
    effectiveFrom: context?.effective_from ?? null,
    effectiveTo: context?.effective_to ?? null,
    isLoading: contextQuery.isLoading || fiscalYearsQuery.isLoading,
    isError: contextQuery.isError || fiscalYearsQuery.isError,
    isSwitching: mutation.isPending,
    setFiscalYear: (fiscalYearId) =>
      mutation.mutate({ fiscal_year_id: fiscalYearId === ALL_PERIODS ? null : fiscalYearId }),
  };
}
