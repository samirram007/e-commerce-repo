import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAccount,
  createJournalEntry,
  fetchAccounts,
  seedDefaultAccounts,
  fetchBalanceSheet,
  fetchGeneralLedger,
  fetchJournalEntries,
  fetchJournalEntry,
  fetchProfitAndLoss,
  fetchTrialBalance,
  reverseJournalEntry,
  type DateRange,
  type FiscalFilter,
} from "./api";
import type { AccountPayload, JournalPayload } from "./schemas";

export const accountingKeys = {
  all: ["accounting"] as const,
  accounts: () => [...accountingKeys.all, "accounts"] as const,
  journals: (filter: FiscalFilter) => [...accountingKeys.all, "journals", filter] as const,
  journal: (id: string) => [...accountingKeys.all, "journal", id] as const,
  trialBalance: (range: DateRange & FiscalFilter) =>
    [...accountingKeys.all, "trial-balance", range] as const,
  profitAndLoss: (fromDate: string, toDate: string) =>
    [...accountingKeys.all, "profit-and-loss", fromDate, toDate] as const,
  balanceSheet: (asOf: string) => [...accountingKeys.all, "balance-sheet", asOf] as const,
  generalLedger: (params: DateRange & FiscalFilter & { accountCode?: string }) =>
    [...accountingKeys.all, "general-ledger", params] as const,
};

export function accountsQueryOptions() {
  return queryOptions({ queryKey: accountingKeys.accounts(), queryFn: fetchAccounts });
}

export function journalEntriesQueryOptions(filter: FiscalFilter = {}) {
  return queryOptions({
    queryKey: accountingKeys.journals(filter),
    queryFn: () => fetchJournalEntries(filter.fiscalYearId),
  });
}

export function journalEntryQueryOptions(id: string) {
  return queryOptions({
    queryKey: accountingKeys.journal(id),
    queryFn: () => fetchJournalEntry(id),
    enabled: Boolean(id),
  });
}

export function trialBalanceQueryOptions(range: DateRange & FiscalFilter = {}) {
  return queryOptions({
    queryKey: accountingKeys.trialBalance(range),
    queryFn: () => fetchTrialBalance(range),
  });
}

export function profitAndLossQueryOptions(fromDate: string, toDate: string) {
  return queryOptions({
    queryKey: accountingKeys.profitAndLoss(fromDate, toDate),
    queryFn: () => fetchProfitAndLoss(fromDate, toDate),
    enabled: Boolean(fromDate && toDate),
  });
}

export function balanceSheetQueryOptions(asOf: string) {
  return queryOptions({
    queryKey: accountingKeys.balanceSheet(asOf),
    queryFn: () => fetchBalanceSheet(asOf),
    enabled: Boolean(asOf),
  });
}

export function generalLedgerQueryOptions(
  params: DateRange & FiscalFilter & { accountCode?: string } = {},
) {
  return queryOptions({
    queryKey: accountingKeys.generalLedger(params),
    queryFn: () => fetchGeneralLedger(params),
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AccountPayload) => createAccount(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountingKeys.accounts() }),
  });
}

export function useSeedDefaultAccounts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: seedDefaultAccounts,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountingKeys.accounts() }),
  });
}

export function useCreateJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: JournalPayload) => createJournalEntry(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountingKeys.all }),
  });
}

export function useReverseJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reverseJournalEntry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountingKeys.all }),
  });
}
