import { z } from "zod";

export const ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"] as const;
export const SIDES = ["debit", "credit"] as const;

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

const decimalInput = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid number");

const positiveDecimalInput = decimalInput.refine((value) => Number(value) > 0, "Must be greater than 0");

export const accountSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  account_type: z.string(),
  normal_side: z.string(),
  is_cash_or_bank: z.boolean(),
  is_system: z.boolean(),
});
export type Account = z.infer<typeof accountSchema>;

export const journalLineSchema = z.object({
  id: z.string(),
  account_code: z.string(),
  account_name: z.string(),
  side: z.string(),
  amount: decimalString,
  description: z.string().nullable(),
  party_ref: z.string().nullable(),
});
export type JournalLine = z.infer<typeof journalLineSchema>;

export const journalEntrySchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  entry_date: z.string(),
  description: z.string().nullable(),
  status: z.string(),
  source_type: z.string(),
  source_id: z.string(),
  reversal_of_id: z.string().nullable(),
  created_by: z.string().nullable(),
  lines: z.array(journalLineSchema),
});
export type JournalEntry = z.infer<typeof journalEntrySchema>;

export const trialBalanceRowSchema = z.object({
  account_code: z.string(),
  account_name: z.string(),
  account_type: z.string(),
  debit: decimalString,
  credit: decimalString,
  balance: decimalString,
});
export type TrialBalanceRow = z.infer<typeof trialBalanceRowSchema>;

export const profitAndLossSchema = z.object({
  from_date: z.string(),
  to_date: z.string(),
  income: decimalString,
  expense: decimalString,
  profit: decimalString,
});
export type ProfitAndLoss = z.infer<typeof profitAndLossSchema>;

export const balanceSheetSchema = z.object({
  as_of: z.string(),
  assets: decimalString,
  liabilities: decimalString,
  equity_total: decimalString,
  balanced: z.boolean(),
});
export type BalanceSheet = z.infer<typeof balanceSheetSchema>;

export const generalLedgerRowSchema = z.object({
  doc_number: z.string(),
  entry_date: z.string(),
  source_type: z.string(),
  account_code: z.string(),
  account_name: z.string(),
  side: z.string(),
  amount: decimalString,
  description: z.string().nullable(),
});
export type GeneralLedgerRow = z.infer<typeof generalLedgerRowSchema>;

// ---- forms ----

export const accountFormSchema = z.object({
  code: z.string().trim().min(1, "Code is required").max(20),
  name: z.string().trim().min(1, "Name is required").max(200),
  account_type: z.enum(ACCOUNT_TYPES),
  normal_side: z.enum(SIDES),
});
export type AccountFormInput = z.input<typeof accountFormSchema>;
export type AccountPayload = z.output<typeof accountFormSchema>;

export const journalLineFormSchema = z.object({
  account_code: z.string().min(1, "Account is required"),
  side: z.enum(SIDES),
  amount: positiveDecimalInput,
  description: z.string().trim().max(500).optional(),
});
export type JournalLineFormInput = z.input<typeof journalLineFormSchema>;
export type JournalLinePayload = z.output<typeof journalLineFormSchema>;

export const journalFormSchema = z.object({
  entry_date: z.string().min(1, "Date is required"),
  description: z.string().trim().max(2000).optional(),
  lines: z.array(journalLineFormSchema).min(2, "A journal needs at least two lines"),
});
export type JournalFormInput = z.input<typeof journalFormSchema>;
export type JournalPayload = z.output<typeof journalFormSchema>;

export const EMPTY_JOURNAL_LINE: JournalLineFormInput = {
  account_code: "",
  side: "debit",
  amount: "0",
  description: "",
};
