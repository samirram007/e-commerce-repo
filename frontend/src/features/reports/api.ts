import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  deliveryPerformanceSchema,
  purchaseSummarySchema,
  salesSummarySchema,
  stockValuationRowSchema,
  type DeliveryPerformance,
  type PurchaseSummary,
  type SalesSummary,
  type StockValuationRow,
} from "./schemas";

export async function fetchSalesSummary(fromDate?: string, toDate?: string): Promise<SalesSummary> {
  const { data } = await api.get("/reports/sales-summary", {
    params: { from_date: fromDate || undefined, to_date: toDate || undefined },
  });
  return salesSummarySchema.parse(data);
}

export async function fetchPurchaseSummary(
  fromDate?: string,
  toDate?: string,
): Promise<PurchaseSummary> {
  const { data } = await api.get("/reports/purchase-summary", {
    params: { from_date: fromDate || undefined, to_date: toDate || undefined },
  });
  return purchaseSummarySchema.parse(data);
}

export async function fetchDeliveryPerformance(): Promise<DeliveryPerformance> {
  const { data } = await api.get("/reports/delivery-performance");
  return deliveryPerformanceSchema.parse(data);
}

export async function fetchStockValuation(): Promise<StockValuationRow[]> {
  const { data } = await api.get("/reports/stock-valuation");
  return z.array(stockValuationRowSchema).parse(data);
}
