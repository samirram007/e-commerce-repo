import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Kpi,
  KpiRow,
  type Column,
} from "../../components/ui";
import { formatMoney, formatQty } from "../../lib/format";
import { reconcileQueryOptions, valuationQueryOptions } from "./queries";
import type { ValuationRow } from "./schemas";

export function ValuationTab() {
  const valuation = useQuery(valuationQueryOptions());
  const reconcile = useQuery(reconcileQueryOptions());

  const columns: Column<ValuationRow>[] = [
    { key: "sku", header: "SKU", render: (r) => <strong>{r.sku}</strong> },
    { key: "avg_cost", header: "Avg cost", align: "right", render: (r) => formatMoney(r.avg_cost) },
    { key: "total_qty", header: "Total qty", align: "right", render: (r) => formatQty(r.total_qty) },
    { key: "total_value", header: "Total value", align: "right", render: (r) => formatMoney(r.total_value) },
  ];

  return (
    <>
      <Card>
        <KpiRow>
          <Kpi
            label="Ledger vs on-hand"
            value={
              reconcile.isLoading ? (
                "…"
              ) : reconcile.error ? (
                <Badge tone="warn">Unavailable</Badge>
              ) : reconcile.data?.balanced ? (
                <Badge tone="ok">Balanced</Badge>
              ) : (
                <Badge tone="bad">Unbalanced</Badge>
              )
            }
            hint="Sum of ledger deltas equals on-hand per product/location"
          />
        </KpiRow>
        <div className="toolbar">
          <Button variant="secondary" onClick={() => reconcile.refetch()} disabled={reconcile.isFetching}>
            {reconcile.isFetching ? "Checking…" : "Run check"}
          </Button>
        </div>
        <ErrorBanner error={reconcile.error} />
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={valuation.data}
          rowKey={(r) => r.product_id}
          loading={valuation.isLoading}
          error={valuation.error}
          onRetry={() => valuation.refetch()}
          empty={<EmptyState title="No valuation" message="Weighted-average costs appear after stock movements." />}
        />
      </Card>
    </>
  );
}
