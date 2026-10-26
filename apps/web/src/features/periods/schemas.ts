import { z } from "zod";

/**
 * Period-context shapes mirroring `apps/api/app/modules/periods/schemas.py`.
 *
 * A *reporting period* is a private, named date range owned by the signed-in
 * user; the *period context* is that user's persisted selection of an active
 * fiscal year / accounting period / reporting period, resolved server-side into
 * one effective date window.
 */

export const fiscalYearOptionSchema = z.object({
  id: z.string(),
  name: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  is_open: z.boolean(),
});
export type FiscalYearOption = z.infer<typeof fiscalYearOptionSchema>;
export const fiscalYearOptionListSchema = z.array(fiscalYearOptionSchema);

export const accountingPeriodOptionSchema = z.object({
  id: z.string(),
  fiscal_year_id: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  is_open: z.boolean(),
});
export type AccountingPeriodOption = z.infer<typeof accountingPeriodOptionSchema>;
export const accountingPeriodOptionListSchema = z.array(accountingPeriodOptionSchema);

export const reportingPeriodSchema = z.object({
  id: z.string(),
  name: z.string(),
  start_date: z.string(),
  end_date: z.string(),
});
export type ReportingPeriod = z.infer<typeof reportingPeriodSchema>;
export const reportingPeriodListSchema = z.array(reportingPeriodSchema);

export const periodContextSchema = z.object({
  fiscal_year: fiscalYearOptionSchema.nullable(),
  accounting_period: accountingPeriodOptionSchema.nullable(),
  reporting_period: reportingPeriodSchema.nullable(),
  // Resolved inclusive window (reporting → accounting → fiscal year).
  effective_from: z.string().nullable(),
  effective_to: z.string().nullable(),
});
export type PeriodContext = z.infer<typeof periodContextSchema>;

/** Payload for `PUT /period-context`; omitted/`null` fields clear that level. */
export interface PeriodContextPayload {
  fiscal_year_id?: string | null;
  accounting_period_id?: string | null;
  reporting_period_id?: string | null;
}

export const reportingPeriodPayloadSchema = z
  .object({
    name: z.string().min(1, "Name is required").max(64),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().min(1, "End date is required"),
  })
  .refine((value) => value.end_date >= value.start_date, {
    message: "End date must be on or after the start date",
    path: ["end_date"],
  });
export type ReportingPeriodPayload = z.infer<typeof reportingPeriodPayloadSchema>;
