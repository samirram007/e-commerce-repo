import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  DataTable,
  EmptyState,
  Field,
  StatusBadge,
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { formatDateTime, formatMoney, formatQty } from "../../lib/format";
import { ledgerQueryOptions, locationOptionsQueryOptions, productOptionsQueryOptions } from "./queries";
import type { LedgerRow } from "./schemas";

const LIMITS = ["50", "100", "200", "500", "1000"] as const;

export function LedgerTab() {
  const [productId, setProductId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [limit, setLimit] = useState<string>("200");

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const ledger = useQuery(
    ledgerQueryOptions({
      productId: productId ?? undefined,
      locationId: locationId ?? undefined,
      limit: Number(limit),
    }),
  );

  const productSelect = useMemo(
    () => (products.data ?? []).map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` })),
    [products.data],
  );
  const locationSelect = useMemo(
    () =>
      (locations.data ?? []).map((l) => ({
        value: l.id,
        label: `${l.code} — ${l.name}`,
        hint: l.location_type,
      })),
    [locations.data],
  );

  const columns: Column<LedgerRow>[] = [
    { key: "moved_at", header: "Moved", render: (r) => formatDateTime(r.moved_at) },
    { key: "type", header: "Movement", render: (r) => <StatusBadge status={r.movement_type} /> },
    { key: "sku", header: "SKU", render: (r) => r.sku },
    { key: "location", header: "Location", render: (r) => r.location_code },
    { key: "qty", header: "Qty", align: "right", render: (r) => formatQty(r.qty_delta) },
    { key: "cost", header: "Unit cost", align: "right", render: (r) => formatMoney(r.unit_cost) },
    { key: "source", header: "Source", render: (r) => r.source_type },
  ];

  return (
    <>
      <Card>
        <div className="form-row">
          <Field label="Product">
            <SheetSelect
              value={productId}
              options={productSelect}
              onChange={setProductId}
              placeholder="All products"
              loading={products.isLoading}
            />
          </Field>
          <Field label="Location">
            <SheetSelect
              value={locationId}
              options={locationSelect}
              onChange={setLocationId}
              placeholder="All locations"
              loading={locations.isLoading}
            />
          </Field>
          <Field label="Limit">
            <SheetSelect
              value={limit}
              options={LIMITS.map((value) => ({ value, label: value }))}
              onChange={setLimit}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={ledger.data}
          rowKey={(r) => r.id}
          loading={ledger.isLoading}
          error={ledger.error}
          onRetry={() => ledger.refetch()}
          empty={<EmptyState title="No movements" message="Stock movements appear here." />}
        />
      </Card>
    </>
  );
}
