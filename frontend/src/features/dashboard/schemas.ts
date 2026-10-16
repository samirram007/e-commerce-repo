import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

/* ---- GET /reports/sales-summary ---- */
export const salesSummarySchema = z.object({
  invoice_count: z.number(),
  total: decimalString,
  tax_total: decimalString,
});
export type SalesSummary = z.infer<typeof salesSummarySchema>;

/* ---- GET /reports/purchase-summary ---- */
export const purchaseSummarySchema = z.object({
  bill_count: z.number(),
  total: decimalString,
});
export type PurchaseSummary = z.infer<typeof purchaseSummarySchema>;

/* ---- GET /reports/delivery-performance ---- */
export const deliveryPerformanceSchema = z.object({
  statuses: z.record(z.string(), z.number()),
  on_time_rate: decimalString,
  failure_count: z.number(),
});
export type DeliveryPerformance = z.infer<typeof deliveryPerformanceSchema>;

/* ---- GET /inventory/valuation ---- */
export const valuationRowSchema = z.object({
  product_id: z.string(),
  sku: z.string(),
  avg_cost: decimalString,
  total_qty: decimalString,
  total_value: decimalString,
});
export type ValuationRow = z.infer<typeof valuationRowSchema>;

export const valuationListSchema = z.array(valuationRowSchema);

/* ---- GET /audit ---- */
export const auditRowSchema = z.object({
  id: z.string(),
  company_id: z.string().nullable(),
  actor_user_id: z.string().nullable(),
  action: z.string(),
  entity_type: z.string(),
  entity_id: z.string().nullable(),
  before_data: z.string().nullable(),
  after_data: z.string().nullable(),
  created_at: z.string(),
});
export type AuditRow = z.infer<typeof auditRowSchema>;

export const auditListSchema = z.array(auditRowSchema);
