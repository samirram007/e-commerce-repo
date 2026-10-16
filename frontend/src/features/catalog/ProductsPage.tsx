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
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatMoney, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  categoriesQueryOptions,
  productsQueryOptions,
  uomsQueryOptions,
  useCreateProduct,
} from "./queries";
import { productFormSchema, STOCK_TYPES, type Product, type ProductFormInput } from "./schemas";

const EMPTY_FORM: ProductFormInput = {
  sku: "",
  name: "",
  description: "",
  category_id: null,
  uom_id: null,
  barcode: "",
  stock_type: "stock",
  base_cost: "0",
  base_price: "0",
  is_sellable: true,
  is_purchasable: true,
  is_active: true,
};

export function ProductsPage() {
  const { has } = usePermissions();
  const canManage = has("catalog.manage");

  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<ProductFormInput>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const products = useQuery(
    productsQueryOptions({ search, categoryId: categoryId ?? undefined }),
  );
  const categories = useQuery(categoriesQueryOptions());
  const uoms = useQuery(uomsQueryOptions());
  const createProduct = useCreateProduct();

  const categoryOptions = useMemo(
    () => (categories.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    [categories.data],
  );
  const uomOptions = useMemo(
    () => (uoms.data ?? []).map((u) => ({ value: u.id, label: `${u.code} — ${u.name}` })),
    [uoms.data],
  );

  function setField<K extends keyof ProductFormInput>(key: K, value: ProductFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function submit() {
    const parsed = productFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createProduct.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_FORM);
      },
    });
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
          {!p.is_active ? <Badge tone="bad">inactive</Badge> : null}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Catalog"
        description="Products, categories and units of measure"
        actions={canManage ? <Button onClick={() => setOpen(true)}>New product</Button> : null}
      />

      <Card>
        <div className="form-row">
          <Field label="Search">
            <Input
              value={search}
              placeholder="SKU or name"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <Field label="Category">
            <SheetSelect
              value={categoryId}
              options={categoryOptions}
              onChange={setCategoryId}
              placeholder="All categories"
              loading={categories.isLoading}
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
        title="New product"
        onClose={() => setOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createProduct.isPending}>
              {createProduct.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createProduct.error} />
        <div className="grid-2">
          <Field label="SKU" error={errors.sku}>
            <Input value={form.sku} onChange={(event) => setField("sku", event.target.value)} />
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
        <div className="grid-2">
          <Field label="Category" error={errors.category_id}>
            <SheetSelect
              value={form.category_id}
              options={categoryOptions}
              onChange={(value) => setField("category_id", value)}
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
        </div>
      </Modal>
    </>
  );
}
