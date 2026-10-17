import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  accountSchema,
  balanceSheetSchema,
  generalLedgerRowSchema,
  journalEntrySchema,
  profitAndLossSchema,
  trialBalanceRowSchema,
  type Account,
  type AccountPayload,
  type BalanceSheet,
  type GeneralLedgerRow,
  type JournalEntry,
  type JournalPayload,
  type ProfitAndLoss,
  type TrialBalanceRow,
} from "./schemas";

export interface DateRange {
  fromDate?: string;
  toDate?: string;
}

/** Filter by the fiscal year an entry posted to (overrides the date range). */
export interface FiscalFilter {
  fiscalYearId?: string;
}

export async function fetchAccounts(): Promise<Account[]> {
  const { data } = await api.get("/accounting/accounts");
  return z.array(accountSchema).parse(data);
}

export async function createAccount(payload: AccountPayload): Promise<Account> {
  const { data } = await api.post("/accounting/accounts", payload);
  return accountSchema.parse(data);
}

/** Idempotently create missing default chart accounts (first-run setup). */
export async function seedDefaultAccounts(): Promise<Account[]> {
  const { data } = await api.post("/accounting/accounts/seed-defaults");
  return z.array(accountSchema).parse(data);
}

export async function fetchJournalEntries(
  fiscalYearId?: string,
): Promise<JournalEntry[]> {
  const { data } = await api.get("/accounting/journal-entries", {
    params: { fiscal_year_id: fiscalYearId || undefined },
  });
  return z.array(journalEntrySchema).parse(data);
}

export async function fetchJournalEntry(id: string): Promise<JournalEntry> {
  const { data } = await api.get(`/accounting/journal-entries/${id}`);
  return journalEntrySchema.parse(data);
}

export async function createJournalEntry(payload: JournalPayload): Promise<JournalEntry> {
  const { data } = await api.post("/accounting/journal-entries", payload);
  return journalEntrySchema.parse(data);
}

export async function reverseJournalEntry(id: string): Promise<JournalEntry> {
  const { data } = await api.post(`/accounting/journal-entries/${id}/reverse`);
  return journalEntrySchema.parse(data);
}

export async function fetchTrialBalance(
  range: DateRange & FiscalFilter = {},
): Promise<TrialBalanceRow[]> {
  const { data } = await api.get("/accounting/reports/trial-balance", {
    params: {
      from_date: range.fromDate || undefined,
      to_date: range.toDate || undefined,
      fiscal_year_id: range.fiscalYearId || undefined,
    },
  });
  return z.array(trialBalanceRowSchema).parse(data);
}

export async function fetchProfitAndLoss(fromDate: string, toDate: string): Promise<ProfitAndLoss> {
  const { data } = await api.get("/accounting/reports/profit-and-loss", {
    params: { from_date: fromDate, to_date: toDate },
  });
  return profitAndLossSchema.parse(data);
}

export async function fetchBalanceSheet(asOf: string): Promise<BalanceSheet> {
  const { data } = await api.get("/accounting/reports/balance-sheet", { params: { as_of: asOf } });
  return balanceSheetSchema.parse(data);
}

export async function fetchGeneralLedger(
  params: DateRange & FiscalFilter & { accountCode?: string } = {},
): Promise<GeneralLedgerRow[]> {
  const { data } = await api.get("/accounting/reports/general-ledger", {
    params: {
      account_code: params.accountCode || undefined,
      from_date: params.fromDate || undefined,
      to_date: params.toDate || undefined,
      fiscal_year_id: params.fiscalYearId || undefined,
    },
  });
  return z.array(generalLedgerRowSchema).parse(data);
}
