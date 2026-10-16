import { api } from "../../lib/api-client";
import {
  auditListSchema,
  deliveryPerformanceSchema,
  purchaseSummarySchema,
  salesSummarySchema,
  valuationListSchema,
  type AuditRow,
  type DeliveryPerformance,
  type PurchaseSummary,
  type SalesSummary,
  type ValuationRow,
} from "./schemas";

/** Read-only dashboard transport: reports + inventory valuation + recent audit. */

export async function fetchSalesSummary(): Promise<SalesSummary> {
  const { data } = await api.get("/reports/sales-summary");
  return salesSummarySchema.parse(data);
}

export async function fetchPurchaseSummary(): Promise<PurchaseSummary> {
  const { data } = await api.get("/reports/purchase-summary");
  return purchaseSummarySchema.parse(data);
}

export async function fetchDeliveryPerformance(): Promise<DeliveryPerformance> {
  const { data } = await api.get("/reports/delivery-performance");
  return deliveryPerformanceSchema.parse(data);
}

export async function fetchStockValuation(): Promise<ValuationRow[]> {
  const { data } = await api.get("/inventory/valuation");
  return valuationListSchema.parse(data);
}

export async function fetchRecentAudit(limit = 10): Promise<AuditRow[]> {
  const { data } = await api.get("/audit", { params: { limit } });
  return auditListSchema.parse(data);
}
