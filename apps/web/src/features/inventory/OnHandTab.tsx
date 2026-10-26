import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  DataTable,
  EmptyState,
  Field,
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { formatQty } from "../../lib/format";
import { locationOptionsQueryOptions, onHandQueryOptions, productOptionsQueryOptions } from "./queries";
import type { OnHandRow } from "./schemas";

export function OnHandTab() {
  const [productId, setProductId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const onHand = useQuery(
    onHandQueryOptions({
      productId: productId ?? undefined,
      locationId: locationId ?? undefined,
    }),
  );

  const productName = useMemo(() => {
    const map = new Map<string, string>();
    for (const product of products.data ?? []) map.set(product.id, `${product.sku} — ${product.name}`);
    return map;
  }, [products.data]);

  const locationLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const location of locations.data ?? []) map.set(location.id, `${location.code} — ${location.name}`);
    return map;
  }, [locations.data]);

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

  const columns: Column<OnHandRow>[] = [
    { key: "product", header: "Product", render: (r) => productName.get(r.product_id) ?? r.product_id },
    { key: "location", header: "Location", render: (r) => locationLabel.get(r.location_id) ?? r.location_id },
    { key: "batch", header: "Batch", render: (r) => r.batch_ref ?? "—" },
    { key: "on_hand", header: "On hand", align: "right", render: (r) => formatQty(r.on_hand) },
    { key: "reserved", header: "Reserved", align: "right", render: (r) => formatQty(r.reserved) },
    { key: "available", header: "Available", align: "right", render: (r) => formatQty(r.available) },
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
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={onHand.data}
          rowKey={(r, index) => `${r.product_id}-${r.location_id}-${r.batch_ref ?? "-"}-${index}`}
          loading={onHand.isLoading}
          error={onHand.error}
          onRetry={() => onHand.refetch()}
          empty={<EmptyState title="No stock on hand" message="Receive or adjust stock to see balances." />}
        />
      </Card>
    </>
  );
}
