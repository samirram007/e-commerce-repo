import { queryOptions } from "@tanstack/react-query";
import {
  fetchDeliveryPerformance,
  fetchPurchaseSummary,
  fetchRecentAudit,
  fetchSalesSummary,
  fetchStockValuation,
} from "./api";

export const dashboardKeys = {
  all: ["dashboard"] as const,
  salesSummary: () => [...dashboardKeys.all, "sales-summary"] as const,
  purchaseSummary: () => [...dashboardKeys.all, "purchase-summary"] as const,
  deliveryPerformance: () => [...dashboardKeys.all, "delivery-performance"] as const,
  valuation: () => [...dashboardKeys.all, "valuation"] as const,
  audit: (limit: number) => [...dashboardKeys.all, "audit", limit] as const,
};

export function salesSummaryQueryOptions() {
  return queryOptions({
    queryKey: dashboardKeys.salesSummary(),
    queryFn: fetchSalesSummary,
  });
}

export function purchaseSummaryQueryOptions() {
  return queryOptions({
    queryKey: dashboardKeys.purchaseSummary(),
    queryFn: fetchPurchaseSummary,
  });
}

export function deliveryPerformanceQueryOptions() {
  return queryOptions({
    queryKey: dashboardKeys.deliveryPerformance(),
    queryFn: fetchDeliveryPerformance,
  });
}

export function stockValuationQueryOptions() {
  return queryOptions({
    queryKey: dashboardKeys.valuation(),
    queryFn: fetchStockValuation,
  });
}

export function recentAuditQueryOptions(limit = 10) {
  return queryOptions({
    queryKey: dashboardKeys.audit(limit),
    queryFn: () => fetchRecentAudit(limit),
  });
}
