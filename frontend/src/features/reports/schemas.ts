import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const salesSummarySchema = z.object({
  invoice_count: z.number(),
  total: decimalString,
  tax_total: decimalString,
});
export type SalesSummary = z.infer<typeof salesSummarySchema>;

export const purchaseSummarySchema = z.object({
  bill_count: z.number(),
  total: decimalString,
});
export type PurchaseSummary = z.infer<typeof purchaseSummarySchema>;

export const deliveryPerformanceSchema = z.object({
  statuses: z.record(z.string(), z.number()),
  on_time_rate: decimalString,
  failure_count: z.number(),
});
export type DeliveryPerformance = z.infer<typeof deliveryPerformanceSchema>;

export const stockValuationRowSchema = z.object({
  product_id: z.string(),
  sku: z.string(),
  avg_cost: decimalString,
  total_qty: decimalString,
  total_value: decimalString,
});
export type StockValuationRow = z.infer<typeof stockValuationRowSchema>;
