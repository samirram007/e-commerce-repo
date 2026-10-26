import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  DataTable,
  EmptyState,
  Kpi,
  KpiRow,
  PageHeader,
  type Column,
} from "../../components/ui";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDateTime, formatMoney, formatQty, titleCase } from "../../lib/format";
import {
  fetchDeliveryPerformance,
  fetchPurchaseSummary,
  fetchRecentAudit,
  fetchSalesSummary,
  fetchStockValuation,
} from "../../features/dashboard/api";
import type { AuditRow, ValuationRow } from "../../features/dashboard/schemas";

const AUDIT_LIMIT = 10;

export function AdminDashboardPage() {
  const { has } = usePermissions();
  const canReports = has("reports.view");
  const canInventory = has("inventory.view");
  const canAudit = has("audit.log.read");

  const sales = useQuery({
    queryKey: ["admin", "sales-summary"],
    queryFn: fetchSalesSummary,
    enabled: canReports,
  });
  const purchases = useQuery({
    queryKey: ["admin", "purchase-summary"],
    queryFn: fetchPurchaseSummary,
    enabled: canReports,
  });
  const delivery = useQuery({
    queryKey: ["admin", "delivery-performance"],
    queryFn: fetchDeliveryPerformance,
    enabled: canReports,
  });
  const valuation = useQuery({
    queryKey: ["admin", "valuation"],
    queryFn: fetchStockValuation,
    enabled: canInventory,
  });
  const audit = useQuery({
    queryKey: ["admin", "audit", AUDIT_LIMIT],
    queryFn: () => fetchRecentAudit(AUDIT_LIMIT),
    enabled: canAudit,
  });

  const stockValue = useMemo(
    () => (valuation.data ?? []).reduce((sum, row) => sum + Number(row.total_value), 0),
    [valuation.data],
  );

  const valuationColumns: Column<ValuationRow>[] = [
    { key: "sku", header: "SKU", render: (row) => <strong>{row.sku}</strong> },
    { key: "qty", header: "Qty", align: "right", render: (row) => formatQty(row.total_qty) },
    { key: "cost", header: "Avg cost", align: "right", render: (row) => formatMoney(row.avg_cost) },
    { key: "value", header: "Value", align: "right", render: (row) => formatMoney(row.total_value) },
  ];

  const auditColumns: Column<AuditRow>[] = [
    {
      key: "created_at",
      header: "When",
      render: (row) => <span className="muted">{formatDateTime(row.created_at)}</span>,
    },
    { key: "action", header: "Action", render: (row) => <strong>{row.action}</strong> },
    { key: "entity_type", header: "Entity", render: (row) => titleCase(row.entity_type) },
    { key: "entity_id", header: "Reference", render: (row) => row.entity_id ?? "—" },
  ];

  return (
    <>
      <PageHeader title="Admin Dashboard" description="Company performance at a glance" />

      <KpiRow>
        <Kpi
          label="Posted sales"
          value={sales.data ? formatMoney(sales.data.total) : "—"}
          hint={
            sales.data
              ? `${sales.data.invoice_count} invoices`
              : canReports
                ? "Loading…"
                : "No permission"
          }
        />
        <Kpi
          label="Posted purchases"
          value={purchases.data ? formatMoney(purchases.data.total) : "—"}
          hint={
            purchases.data
              ? `${purchases.data.bill_count} bills`
              : canReports
                ? "Loading…"
                : "No permission"
          }
        />
        <Kpi
          label="On-time delivery"
          value={delivery.data ? `${formatQty(delivery.data.on_time_rate)}%` : "—"}
          hint={
            delivery.data
              ? `${delivery.data.failure_count} failed shipments`
              : canReports
                ? "Loading…"
                : "No permission"
          }
        />
        <Kpi
          label="Stock value"
          value={valuation.data ? formatMoney(stockValue) : "—"}
          hint={
            valuation.data
              ? `${valuation.data.length} products`
              : canInventory
                ? "Loading…"
                : "No permission"
          }
        />
      </KpiRow>

      <Card title="Stock valuation">
        <DataTable
          columns={valuationColumns}
          rows={valuation.data}
          rowKey={(row) => row.product_id}
          loading={valuation.isLoading}
          error={valuation.error}
          onRetry={() => valuation.refetch()}
          empty={
            <EmptyState
              title="No stock valuation"
              message={canInventory ? "Nothing has been stocked yet." : "You need permission to view inventory."}
            />
          }
        />
      </Card>

      <Card title="Recent activity">
        <DataTable
          columns={auditColumns}
          rows={audit.data}
          rowKey={(row) => row.id}
          loading={audit.isLoading}
          error={audit.error}
          onRetry={() => audit.refetch()}
          empty={
            <EmptyState
              title="No recent activity"
              message={canAudit ? "Audit entries will appear here." : "You need permission to view the audit log."}
            />
          }
        />
      </Card>
    </>
  );
}