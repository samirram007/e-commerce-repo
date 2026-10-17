import { api } from "../../lib/api-client";
import {
  accountingPeriodOptionListSchema,
  fiscalYearOptionListSchema,
  periodContextSchema,
  reportingPeriodListSchema,
  reportingPeriodSchema,
  type AccountingPeriodOption,
  type FiscalYearOption,
  type PeriodContext,
  type PeriodContextPayload,
  type ReportingPeriod,
  type ReportingPeriodPayload,
} from "./schemas";

/**
 * Period-context endpoints. All are available to any member of the active
 * company (a period context is a personal preference, not an admin setting) —
 * unlike `GET /fiscal-years`, which requires `fiscal.manage`.
 */

export async function fetchPeriodContext(): Promise<PeriodContext> {
  const { data } = await api.get("/period-context");
  return periodContextSchema.parse(data);
}

export async function setPeriodContext(input: PeriodContextPayload): Promise<PeriodContext> {
  const { data } = await api.put("/period-context", input);
  return periodContextSchema.parse(data);
}

export async function fetchFiscalYearOptions(): Promise<FiscalYearOption[]> {
  const { data } = await api.get("/period-context/fiscal-years");
  return fiscalYearOptionListSchema.parse(data);
}

export async function fetchAccountingPeriodOptions(
  fiscalYearId: string,
): Promise<AccountingPeriodOption[]> {
  const { data } = await api.get(`/period-context/fiscal-years/${fiscalYearId}/periods`);
  return accountingPeriodOptionListSchema.parse(data);
}

/* ---- reporting periods (per-user saved ranges) ---- */

export async function fetchReportingPeriods(): Promise<ReportingPeriod[]> {
  const { data } = await api.get("/reporting-periods");
  return reportingPeriodListSchema.parse(data);
}

export async function createReportingPeriod(
  input: ReportingPeriodPayload,
): Promise<ReportingPeriod> {
  const { data } = await api.post("/reporting-periods", input);
  return reportingPeriodSchema.parse(data);
}

export async function updateReportingPeriod(
  id: string,
  input: ReportingPeriodPayload,
): Promise<ReportingPeriod> {
  const { data } = await api.patch(`/reporting-periods/${id}`, input);
  return reportingPeriodSchema.parse(data);
}

export async function deleteReportingPeriod(id: string): Promise<void> {
  await api.delete(`/reporting-periods/${id}`);
}
