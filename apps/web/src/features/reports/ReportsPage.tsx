import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Kpi,
  KpiRow,
  PageHeader,
  StatusBadge,
  type Column,
} from "../../components/ui";
import { formatMoney, formatQty } from "../../lib/format";
import {
  deliveryPerformanceQueryOptions,
  purchaseSummaryQueryOptions,
  salesSummaryQueryOptions,
  stockValuationQueryOptions,
} from "./queries";
import type { StockValuationRow } from "./schemas";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function startOfYear(): string {
  return `${new Date().getFullYear()}-01-01`;
}

export function ReportsPage() {
  const [fromDate, setFromDate] = useState(startOfYear());
  const [toDate, setToDate] = useState(today());

  const range = useMemo(
    () => ({ fromDate: fromDate || undefined, toDate: toDate || undefined }),
    [fromDate, toDate],
  );

  const sales = useQuery(salesSummaryQueryOptions(range));
  const purchases = useQuery(purchaseSummaryQueryOptions(range));
  const delivery = useQuery(deliveryPerformanceQueryOptions());
  const valuation = useQuery(stockValuationQueryOptions());

  const deliveryRows = useMemo(
    () =>
      Object.entries(delivery.data?.statuses ?? {}).map(([status, count]) => ({ status, count })),
    [delivery.data],
  );

  const deliveryColumns: Column<(typeof deliveryRows)[number]>[] = [
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "count", header: "Shipments", align: "right", render: (r) => formatQty(r.count) },
  ];

  const valuationColumns: Column<StockValuationRow>[] = [
    { key: "sku", header: "SKU", render: (r) => <strong>{r.sku}</strong> },
    { key: "qty", header: "On hand", align: "right", render: (r) => formatQty(r.total_qty) },
    { key: "avg_cost", header: "Avg cost", align: "right", render: (r) => formatMoney(r.avg_cost) },
    { key: "value", header: "Value", align: "right", render: (r) => formatMoney(r.total_value) },
  ];

  return (
    <>
      <PageHeader title="Reports" description="Sales, purchasing, fulfillment and stock valuation" />

      <Card>
        <div className="form-row">
          <Field label="From">
            <Input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </Field>
        </div>
      </Card>

      <ErrorBanner error={sales.error ?? purchases.error} />

      <Card title="Sales summary">
        <KpiRow>
          <Kpi label="Invoices" value={sales.data?.invoice_count ?? "—"} />
          <Kpi label="Total sales" value={formatMoney(sales.data?.total)} />
          <Kpi label="Tax collected" value={formatMoney(sales.data?.tax_total)} />
        </KpiRow>
      </Card>

      <Card title="Purchase summary">
        <KpiRow>
          <Kpi label="Bills" value={purchases.data?.bill_count ?? "—"} />
          <Kpi label="Total purchases" value={formatMoney(purchases.data?.total)} />
        </KpiRow>
      </Card>

      <Card title="Delivery performance">
        <ErrorBanner error={delivery.error} />
        <KpiRow>
          <Kpi label="On-time rate" value={`${formatQty(delivery.data?.on_time_rate)}%`} />
          <Kpi label="Failures" value={delivery.data?.failure_count ?? "—"} />
        </KpiRow>
        <DataTable
          columns={deliveryColumns}
          rows={deliveryRows}
          rowKey={(r) => r.status}
          loading={delivery.isLoading}
          error={delivery.error}
          onRetry={() => delivery.refetch()}
          empty={<EmptyState title="No shipments" message="Nothing to report yet." />}
        />
      </Card>

      <Card title="Stock valuation">
        <DataTable
          columns={valuationColumns}
          rows={valuation.data}
          rowKey={(r) => r.product_id}
          loading={valuation.isLoading}
          error={valuation.error}
          onRetry={() => valuation.refetch()}
          empty={<EmptyState title="No stock" message="No valued inventory." />}
        />
      </Card>
    </>
  );
}
