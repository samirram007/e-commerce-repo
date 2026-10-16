import { queryOptions } from "@tanstack/react-query";
import {
  fetchDeliveryPerformance,
  fetchPurchaseSummary,
  fetchSalesSummary,
  fetchStockValuation,
} from "./api";

export interface ReportRange {
  fromDate?: string;
  toDate?: string;
}

export const reportsKeys = {
  all: ["reports"] as const,
  salesSummary: (range: ReportRange) => [...reportsKeys.all, "sales-summary", range] as const,
  purchaseSummary: (range: ReportRange) => [...reportsKeys.all, "purchase-summary", range] as const,
  deliveryPerformance: () => [...reportsKeys.all, "delivery-performance"] as const,
  stockValuation: () => [...reportsKeys.all, "stock-valuation"] as const,
};

export function salesSummaryQueryOptions(range: ReportRange = {}) {
  return queryOptions({
    queryKey: reportsKeys.salesSummary(range),
    queryFn: () => fetchSalesSummary(range.fromDate, range.toDate),
  });
}

export function purchaseSummaryQueryOptions(range: ReportRange = {}) {
  return queryOptions({
    queryKey: reportsKeys.purchaseSummary(range),
    queryFn: () => fetchPurchaseSummary(range.fromDate, range.toDate),
  });
}

export function deliveryPerformanceQueryOptions() {
  return queryOptions({
    queryKey: reportsKeys.deliveryPerformance(),
    queryFn: fetchDeliveryPerformance,
  });
}

export function stockValuationQueryOptions() {
  return queryOptions({
    queryKey: reportsKeys.stockValuation(),
    queryFn: fetchStockValuation,
  });
}
