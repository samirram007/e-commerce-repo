import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge, Card, DataTable, EmptyState, Field, Input, type Column } from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { locationOptionsQueryOptions, productOptionsQueryOptions, serialsQueryOptions } from "./queries";
import { SERIAL_STATUSES, type SerialRow } from "./schemas";

export function SerialsTab() {
  const [productId, setProductId] = useState<string | null>(null);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const serials = useQuery(
    serialsQueryOptions({
      productId: productId ?? undefined,
      locationId: locationId ?? undefined,
      status: status ?? undefined,
      search: search.trim() || undefined,
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
  const statusSelect = useMemo(
    () => SERIAL_STATUSES.map((s) => ({ value: s, label: s === "in_stock" ? "In stock" : "Issued" })),
    [],
  );

  const columns: Column<SerialRow>[] = [
    { key: "serial", header: "Serial number", render: (r) => <strong>{r.serial_number}</strong> },
    { key: "sku", header: "Product", render: (r) => r.sku },
    { key: "location", header: "Location", render: (r) => r.location_code },
    { key: "batch", header: "Batch", render: (r) => r.batch_ref ?? "—" },
    {
      key: "status",
      header: "Status",
      render: (r) => (r.status === "in_stock" ? <Badge tone="ok">in stock</Badge> : <Badge>issued</Badge>),
    },
    {
      key: "issued_at",
      header: "Issued",
      render: (r) => (r.issued_at ? new Date(r.issued_at).toLocaleDateString() : "—"),
    },
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
          <Field label="Status">
            <SheetSelect
              value={status}
              options={statusSelect}
              onChange={setStatus}
              placeholder="All statuses"
            />
          </Field>
          <Field label="Serial number">
            <Input
              value={search}
              placeholder="Search serials"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={serials.data}
          rowKey={(r) => r.id}
          loading={serials.isLoading}
          error={serials.error}
          onRetry={() => serials.refetch()}
          empty={
            <EmptyState
              title="No serial numbers"
              message="Receive a serial-tracked product to register its serial numbers here."
            />
          }
        />
      </Card>
    </>
  );
}
