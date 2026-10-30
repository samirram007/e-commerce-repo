import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Modal,
  PageHeader,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatMoney, formatQty, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  locationOptionsQueryOptions,
  onHandQueryOptions,
} from "../inventory/queries";
import type { OnHandRow } from "../inventory/schemas";
import {
  categoriesQueryOptions,
  productsQueryOptions,
  uomsQueryOptions,
  useCreateProduct,
  useUpdateProduct,
} from "./queries";
import { productFormSchema, STOCK_TYPES, type Product, type ProductFormInput } from "./schemas";

const EMPTY_FORM: ProductFormInput = {
  sku: "",
  name: "",
  description: "",
  category_id: null,
  uom_id: null,
  barcode: "",
  hsn_sac: "",
  stock_type: "stock",
  track_batches: false,
  track_serials: false,
  base_cost: "0",
  base_price: "0",
  weight_kg: "",
  length_cm: "",
  width_cm: "",
  height_cm: "",
  is_sellable: true,
  is_purchasable: true,
  is_active: true,
};

function formFromProduct(product: Product): ProductFormInput {
  return {
    sku: product.sku,
    name: product.name,
    description: product.description ?? "",
    category_id: product.category_id,
    uom_id: product.uom_id,
    barcode: product.barcode ?? "",
    hsn_sac: product.hsn_sac ?? "",
    stock_type: product.stock_type as ProductFormInput["stock_type"],
    track_batches: product.track_batches,
    track_serials: product.track_serials,
    base_cost: product.base_cost,
    base_price: product.base_price,
    weight_kg: product.weight_kg ?? "",
    length_cm: product.length_cm ?? "",
    width_cm: product.width_cm ?? "",
    height_cm: product.height_cm ?? "",
    is_sellable: product.is_sellable,
    is_purchasable: product.is_purchasable,
    is_active: product.is_active,
  };
}

export function ProductsPage() {
  const { has } = usePermissions();
  const canManage = has("catalog.manage");
  const canViewStock = has("inventory.view");

  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [stockType, setStockType] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductFormInput>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Stock-on-hand detail for one product (inventory.view only).
  const [stockFor, setStockFor] = useState<Product | null>(null);

  const products = useQuery(
    productsQueryOptions({
      search,
      categoryId: categoryId ?? undefined,
      stockType: stockType ?? undefined,
      isActive: activeFilter ?? undefined,
    }),
  );
  const categories = useQuery(categoriesQueryOptions());
  const uoms = useQuery(uomsQueryOptions());
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();

  const stock = useQuery({
    ...onHandQueryOptions({ productId: stockFor?.id ?? "" }),
    enabled: stockFor !== null,
  });
  const locations = useQuery({
    ...locationOptionsQueryOptions(),
    enabled: stockFor !== null,
  });
  const locationLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const location of locations.data ?? []) {
      map.set(location.id, `${location.code} — ${location.name}`);
    }
    return map;
  }, [locations.data]);

  const categoryOptions = useMemo(
    () => [
      { value: "", label: "All categories" },
      ...(categories.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    ],
    [categories.data],
  );
  const stockTypeOptions = useMemo(
    () => [
      { value: "", label: "All types" },
      ...STOCK_TYPES.map((type) => ({ value: type, label: titleCase(type) })),
    ],
    [],
  );
  const activeOptions = useMemo(
    () => [
      { value: "", label: "All products" },
      { value: "true", label: "Active" },
      { value: "false", label: "Inactive" },
    ],
    [],
  );
  const uomOptions = useMemo(
    () => (uoms.data ?? []).map((u) => ({ value: u.id, label: `${u.code} — ${u.name}` })),
    [uoms.data],
  );

  function setField<K extends keyof ProductFormInput>(key: K, value: ProductFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setErrors({});
    setOpen(true);
  }

  function openEdit(product: Product) {
    setEditing(product);
    setForm(formFromProduct(product));
    setErrors({});
    setOpen(true);
  }

  function submit() {
    const parsed = productFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    if (editing) {
      // PATCH body has no sku — the code is immutable after creation.
      const { sku: _sku, ...patch } = parsed.data;
      updateProduct.mutate(
        { id: editing.id, input: patch },
        { onSuccess: () => setOpen(false) },
      );
      return;
    }
    createProduct.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_FORM);
      },
    });
  }

  function toggleActive(product: Product) {
    updateProduct.mutate({ id: product.id, input: { is_active: !product.is_active } });
  }

  const columns: Column<Product>[] = [
    { key: "sku", header: "SKU", render: (p) => <strong>{p.sku}</strong> },
    { key: "name", header: "Name", render: (p) => p.name },
    { key: "stock_type", header: "Type", render: (p) => titleCase(p.stock_type) },
    { key: "cost", header: "Cost", align: "right", render: (p) => formatMoney(p.base_cost) },
    { key: "price", header: "Price", align: "right", render: (p) => formatMoney(p.base_price) },
    {
      key: "flags",
      header: "Flags",
      render: (p) => (
        <span className="table-actions">
          {p.is_sellable ? <Badge tone="ok">sellable</Badge> : null}
          {p.is_purchasable ? <Badge>purchasable</Badge> : null}
          {p.track_batches ? <Badge>batch</Badge> : null}
          {p.track_serials ? <Badge>serial</Badge> : null}
          {!p.is_active ? <Badge tone="bad">inactive</Badge> : null}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (p) =>
        canManage || canViewStock ? (
          <span className="table-actions">
            {canViewStock && p.stock_type === "stock" ? (
              <Button variant="secondary" onClick={() => setStockFor(p)}>
                Stock
              </Button>
            ) : null}
            {canManage ? (
              <>
                <Button variant="secondary" onClick={() => openEdit(p)}>
                  Edit
                </Button>
                <Button
                  variant={p.is_active ? "danger" : "secondary"}
                  onClick={() => toggleActive(p)}
                  disabled={updateProduct.isPending}
                >
                  {p.is_active ? "Deactivate" : "Reactivate"}
                </Button>
              </>
            ) : null}
          </span>
        ) : null,
    },
  ];

  const stockColumns: Column<OnHandRow>[] = [
    { key: "location", header: "Location", render: (r) => locationLabel.get(r.location_id) ?? r.location_id },
    { key: "batch", header: "Batch", render: (r) => r.batch_ref ?? "—" },
    { key: "on_hand", header: "On hand", align: "right", render: (r) => formatQty(r.on_hand) },
    { key: "reserved", header: "Reserved", align: "right", render: (r) => formatQty(r.reserved) },
    { key: "available", header: "Available", align: "right", render: (r) => formatQty(r.available) },
  ];

  return (
    <>
      <PageHeader
        title="Catalog"
        description="Products, categories and units of measure"
        actions={canManage ? <Button onClick={openCreate}>New product</Button> : null}
      />

      <Card>
        <div className="form-row">
          <Field label="Search">
            <Input
              value={search}
              placeholder="SKU, name or barcode"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <Field label="Category">
            <SheetSelect
              value={categoryId ?? ""}
              options={categoryOptions}
              onChange={(value) => setCategoryId(value || null)}
              placeholder="All categories"
              loading={categories.isLoading}
            />
          </Field>
          <Field label="Stock type">
            <SheetSelect
              value={stockType ?? ""}
              options={stockTypeOptions}
              onChange={(value) => setStockType(value || null)}
              placeholder="All types"
            />
          </Field>
          <Field label="Status">
            <SheetSelect
              value={activeFilter ?? ""}
              options={activeOptions}
              onChange={(value) => setActiveFilter(value || null)}
              placeholder="All products"
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={products.data?.items}
          rowKey={(p) => p.id}
          loading={products.isLoading}
          error={products.error}
          onRetry={() => products.refetch()}
          empty={<EmptyState title="No products" message="Create your first product." />}
        />
      </Card>

      <Modal
        open={open}
        title={editing ? `Edit ${editing.sku}` : "New product"}
        onClose={() => setOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createProduct.isPending || updateProduct.isPending}>
              {createProduct.isPending || updateProduct.isPending
                ? "Saving…"
                : editing
                  ? "Save"
                  : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={editing ? updateProduct.error : createProduct.error} />
        <div className="grid-2">
          <Field
            label="SKU"
            error={errors.sku}
            hint={editing ? "The SKU cannot be changed after creation." : undefined}
          >
            <Input
              value={form.sku}
              disabled={editing !== null}
              onChange={(event) => setField("sku", event.target.value)}
            />
          </Field>
          <Field label="Name" error={errors.name}>
            <Input value={form.name} onChange={(event) => setField("name", event.target.value)} />
          </Field>
        </div>
        <Field label="Description" error={errors.description}>
          <Input
            value={form.description ?? ""}
            onChange={(event) => setField("description", event.target.value)}
          />
        </Field>
        <Field
          label="HSN / SAC"
          error={errors.hsn_sac}
          hint="Printed on GST invoices — 4 to 8 digits."
        >
          <Input
            value={form.hsn_sac ?? ""}
            onChange={(event) => setField("hsn_sac", event.target.value)}
          />
        </Field>
        <div className="grid-2">
          <Field label="Category" error={errors.category_id}>
            <SheetSelect
              value={form.category_id}
              options={categoryOptions}
              onChange={(value) => setField("category_id", value || null)}
              loading={categories.isLoading}
            />
          </Field>
          <Field label="Unit of measure" error={errors.uom_id}>
            <SheetSelect
              value={form.uom_id}
              options={uomOptions}
              onChange={(value) => setField("uom_id", value)}
              loading={uoms.isLoading}
            />
          </Field>
        </div>
        <div className="grid-3">
          <Field label="Stock type" error={errors.stock_type}>
            <SheetSelect
              value={form.stock_type}
              options={STOCK_TYPES.map((s) => ({ value: s, label: titleCase(s) }))}
              onChange={(value) => setField("stock_type", value as ProductFormInput["stock_type"])}
            />
          </Field>
          <Field label="Base cost" error={errors.base_cost}>
            <Input
              value={form.base_cost}
              onChange={(event) => setField("base_cost", event.target.value)}
            />
          </Field>
          <Field label="Base price" error={errors.base_price}>
            <Input
              value={form.base_price}
              onChange={(event) => setField("base_price", event.target.value)}
            />
          </Field>
        </div>
        <h3 className="section-title">Shipping</h3>
        <p className="muted">
          Carriers rate a parcel by its weight and size; leave a field blank if it does not apply
          (services need no measurements).
        </p>
        <div className="measure-grid">
          <Field label="Weight (kg)" error={errors.weight_kg}>
            <Input
              value={form.weight_kg}
              inputMode="decimal"
              placeholder="0.500"
              onChange={(event) => setField("weight_kg", event.target.value)}
            />
          </Field>
          <Field label="Length (cm)" error={errors.length_cm}>
            <Input
              value={form.length_cm}
              inputMode="decimal"
              onChange={(event) => setField("length_cm", event.target.value)}
            />
          </Field>
          <Field label="Width (cm)" error={errors.width_cm}>
            <Input
              value={form.width_cm}
              inputMode="decimal"
              onChange={(event) => setField("width_cm", event.target.value)}
            />
          </Field>
          <Field label="Height (cm)" error={errors.height_cm}>
            <Input
              value={form.height_cm}
              inputMode="decimal"
              onChange={(event) => setField("height_cm", event.target.value)}
            />
          </Field>
        </div>
        <div className="toolbar">
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_sellable}
              onChange={(event) => setField("is_sellable", event.target.checked)}
            />
            Sellable
          </label>
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_purchasable}
              onChange={(event) => setField("is_purchasable", event.target.checked)}
            />
            Purchasable
          </label>
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setField("is_active", event.target.checked)}
            />
            Active
          </label>
          <label className="pill">
            <input
              type="checkbox"
              checked={form.track_batches}
              disabled={form.stock_type !== "stock"}
              onChange={(event) => setField("track_batches", event.target.checked)}
            />
            Track batches
          </label>
          <label className="pill">
            <input
              type="checkbox"
              checked={form.track_serials}
              disabled={form.stock_type !== "stock"}
              onChange={(event) => setField("track_serials", event.target.checked)}
            />
            Track serials
          </label>
        </div>
      </Modal>

      {/* ------------------------------------------- stock on-hand sheet */}
      <Sheet
        open={stockFor !== null}
        title={stockFor ? `Stock — ${stockFor.sku} ${stockFor.name}` : "Stock"}
        onClose={() => setStockFor(null)}
      >
        <div style={{ padding: 18 }}>
          <ErrorBanner error={stock.error ?? locations.error} />
          {stockFor ? (
            <div className="grid-2" style={{ marginBottom: 14 }}>
              <div>
                <div className="muted">On hand (total)</div>
                <div>
                  {formatQty(
                    (stock.data ?? []).reduce(
                      (sum, row) => sum + (Number(row.on_hand) || 0),
                      0,
                    ),
                  )}
                </div>
              </div>
              <div>
                <div className="muted">Available (total)</div>
                <div>
                  {formatQty(
                    (stock.data ?? []).reduce(
                      (sum, row) => sum + (Number(row.available) || 0),
                      0,
                    ),
                  )}
                </div>
              </div>
            </div>
          ) : null}
          <DataTable
            columns={stockColumns}
            rows={stock.data}
            rowKey={(row, index) => `${row.location_id}-${row.batch_ref ?? "-"}-${index}`}
            loading={stock.isLoading}
            onRetry={() => stock.refetch()}
            empty={
              <EmptyState
                title="No stock yet"
                message="Receive or adjust stock to see balances here."
              />
            }
          />
        </div>
      </Sheet>
    </>
  );
}
