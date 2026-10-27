import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, PageHeader, StatusBadge } from "../../components/ui";
import { ServerDataTable, type ServerColumn } from "../../components/data-table";
import { CrudFormModal, useCrudForm, type FormFieldSpec } from "../../components/crud-form";
import { useListState } from "../../hooks/use-list-state";
import { usePermissions } from "../../hooks/use-permissions";
import { categoriesQueryOptions, productsQueryOptions } from "../catalog/queries";
import { formatDate, formatMoney, titleCase } from "../../lib/format";
import {
  couponsQueryOptions,
  redemptionsQueryOptions,
  useCreateCoupon,
  useDeactivateCoupon,
  useUpdateCoupon,
} from "./queries";
import {
  COUPON_KINDS,
  COUPON_SCOPES,
  couponFormSchema,
  type Coupon,
  type CouponFormInput,
} from "./schemas";

const EMPTY_FORM: CouponFormInput = {
  code: "",
  description: "",
  kind: "percent",
  value: "10",
  max_discount: "",
  min_subtotal: "",
  scope: "order",
  category_id: "",
  product_id: "",
  starts_at: "",
  ends_at: "",
  max_redemptions: "",
  max_per_customer: "",
  is_active: true,
};

const KIND_OPTIONS = COUPON_KINDS.map((kind) => ({ value: kind, label: titleCase(kind) }));

const SCOPE_LABELS: Record<(typeof COUPON_SCOPES)[number], string> = {
  order: "Whole order",
  category: "One category",
  product: "One product",
};

const SCOPE_OPTIONS = COUPON_SCOPES.map((scope) => ({ value: scope, label: SCOPE_LABELS[scope] }));

/** ISO timestamps become the `YYYY-MM-DD` the date inputs expect. */
function dateInput(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

function formFromCoupon(coupon: Coupon): CouponFormInput {
  return {
    code: coupon.code,
    description: coupon.description ?? "",
    kind: coupon.kind,
    value: coupon.value,
    max_discount: coupon.max_discount ?? "",
    min_subtotal: coupon.min_subtotal,
    scope: coupon.scope,
    category_id: coupon.category_id ?? "",
    product_id: coupon.product_id ?? "",
    starts_at: dateInput(coupon.starts_at),
    ends_at: dateInput(coupon.ends_at),
    max_redemptions: coupon.max_redemptions === null ? "" : String(coupon.max_redemptions),
    max_per_customer: coupon.max_per_customer === null ? "" : String(coupon.max_per_customer),
    is_active: coupon.is_active,
  };
}

function valueLabel(coupon: Coupon): string {
  // Decimal strings arrive as "10.0000"; show the plain number.
  return coupon.kind === "percent" ? `${Number(coupon.value)}%` : formatMoney(coupon.value);
}

/** Recent redemptions for one code — who used it, on which order, for how much. */
function Redemptions({ coupon }: { coupon: Coupon }) {
  const ledger = useQuery(redemptionsQueryOptions(coupon.id));
  if (ledger.isLoading) return <div className="muted">Loading…</div>;
  if (!ledger.data || ledger.data.length === 0) return <div className="muted">Not used yet.</div>;
  return (
    <div className="muted" style={{ marginTop: 6 }}>
      {ledger.data.slice(0, 5).map((row) => (
        <div key={row.id}>
          {row.customer_key ?? "guest shopper"} · -{formatMoney(row.amount)} ·{" "}
          {formatDate(row.redeemed_at)}
        </div>
      ))}
      {ledger.data.length > 5 ? <div>…and {ledger.data.length - 5} more</div> : null}
    </div>
  );
}

export function CouponsPage() {
  const { has } = usePermissions();
  const canManage = has("promotions.manage");

  // One server-side list state: pagination, sort and debounced search.
  const list = useListState({ sort: "code", order: "asc" });
  const coupons = useQuery(couponsQueryOptions(list.state));
  const categories = useQuery(categoriesQueryOptions());
  const products = useQuery(productsQueryOptions({}));

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Coupon | null>(null);
  const [history, setHistory] = useState<string | null>(null);

  const createCoupon = useCreateCoupon();
  const updateCoupon = useUpdateCoupon();
  const deactivateCoupon = useDeactivateCoupon();
  const mutationError = createCoupon.error ?? updateCoupon.error ?? deactivateCoupon.error;

  const categoryNames = new Map((categories.data ?? []).map((row) => [row.id, row.name]));
  const productNames = new Map((products.data?.items ?? []).map((row) => [row.id, row.name]));

  const form = useCrudForm({
    schema: couponFormSchema,
    initialValues: EMPTY_FORM,
    onSubmit: (values) => {
      if (editing) {
        updateCoupon.mutate(
          { id: editing.id, input: values },
          { onSuccess: () => setModalOpen(false) },
        );
        return;
      }
      createCoupon.mutate(values, { onSuccess: () => setModalOpen(false) });
    },
  });

  function openCreate() {
    setEditing(null);
    form.reset(EMPTY_FORM);
    setModalOpen(true);
  }

  function openEdit(coupon: Coupon) {
    setEditing(coupon);
    form.reset(formFromCoupon(coupon));
    setModalOpen(true);
  }

  const scopeLabel = (coupon: Coupon): string => {
    if (coupon.scope === "category") {
      return categoryNames.get(coupon.category_id ?? "") ?? "Selected category";
    }
    if (coupon.scope === "product") {
      return productNames.get(coupon.product_id ?? "") ?? "Selected product";
    }
    return SCOPE_LABELS.order;
  };

  const columns: ServerColumn<Coupon>[] = [
    {
      key: "code",
      header: "Code",
      sortKey: "code",
      render: (coupon) => (
        <>
          <strong>{coupon.code}</strong>
          {coupon.description ? <div className="muted">{coupon.description}</div> : null}
        </>
      ),
    },
    { key: "value", header: "Discount", sortKey: "value", render: valueLabel },
    { key: "scope", header: "Applies to", render: scopeLabel },
    {
      key: "minimum",
      header: "Minimum order",
      align: "right",
      render: (coupon) =>
        Number(coupon.min_subtotal) > 0 ? formatMoney(coupon.min_subtotal) : "—",
    },
    {
      key: "usage",
      header: "Used",
      align: "right",
      render: (coupon) => (
        <>
          <span
            onClick={() => setHistory(history === coupon.id ? null : coupon.id)}
            style={{ cursor: "pointer", textDecoration: "underline dotted" }}
            title="Show recent redemptions"
          >
            {coupon.redemptions}
            {coupon.max_redemptions === null ? "" : ` / ${coupon.max_redemptions}`}
          </span>
          {coupon.redemptions > 0 ? (
            <div className="muted">-{formatMoney(coupon.redeemed_amount)}</div>
          ) : null}
          {history === coupon.id ? <Redemptions coupon={coupon} /> : null}
        </>
      ),
    },
    {
      key: "window",
      header: "Status",
      render: (coupon) => (
        <>
          <StatusBadge status={coupon.is_active ? "active" : "inactive"} />
          <div className="muted">
            {coupon.ends_at ? `ends ${formatDate(coupon.ends_at)}` : "no end date"}
          </div>
        </>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (coupon) =>
        canManage ? (
          <div style={{ display: "flex", gap: 6 }}>
            <Button variant="secondary" onClick={() => openEdit(coupon)}>
              Edit
            </Button>
            {coupon.is_active ? (
              <Button
                variant="secondary"
                onClick={() => deactivateCoupon.mutate(coupon.id)}
                disabled={deactivateCoupon.isPending}
              >
                Deactivate
              </Button>
            ) : null}
          </div>
        ) : null,
    },
  ];

  const fields: FormFieldSpec[] = [
    {
      name: "code",
      label: "Code",
      placeholder: "WELCOME10",
      disabled: editing !== null,
      hint: editing ? "A code cannot be renamed" : "Shoppers type this at checkout",
    },
    { name: "description", label: "Description", placeholder: "10% welcome offer" },
    { name: "kind", label: "Type", type: "select", options: KIND_OPTIONS },
    {
      name: "value",
      label: form.values.kind === "fixed" ? "Amount off" : "Percentage off",
      type: "money" as const,
      placeholder: form.values.kind === "fixed" ? "100" : "10",
    },
    {
      name: "max_discount",
      label: "Maximum discount",
      type: "money" as const,
      placeholder: "No cap",
      hint: "Caps a percentage coupon",
    },
    {
      name: "min_subtotal",
      label: "Minimum order",
      type: "money" as const,
      placeholder: "0",
    },
    { name: "scope", label: "Applies to", type: "select", options: SCOPE_OPTIONS },
    ...(form.values.scope === "category"
      ? [
          {
            name: "category_id",
            label: "Category",
            type: "select" as const,
            options: (categories.data ?? []).map((row) => ({ value: row.id, label: row.name })),
          },
        ]
      : []),
    ...(form.values.scope === "product"
      ? [
          {
            name: "product_id",
            label: "Product",
            type: "select" as const,
            options: (products.data?.items ?? []).map((row) => ({
              value: row.id,
              label: `${row.sku} · ${row.name}`,
            })),
          },
        ]
      : []),
    { name: "starts_at", label: "Starts", placeholder: "YYYY-MM-DD" },
    { name: "ends_at", label: "Ends", placeholder: "YYYY-MM-DD" },
    { name: "max_redemptions", label: "Total uses", placeholder: "Unlimited" },
    { name: "max_per_customer", label: "Uses per customer", placeholder: "Unlimited" },
    { name: "is_active", label: "Status", type: "checkbox", placeholder: "Active at checkout" },
  ];

  return (
    <>
      <PageHeader
        title="Coupons"
        description="Promo codes shoppers redeem at checkout, with limits and an audit trail"
        actions={canManage ? <Button onClick={openCreate}>New coupon</Button> : null}
      />

      <Card>
        <ServerDataTable
          columns={columns}
          rows={coupons.data?.items}
          rowKey={(coupon) => coupon.id}
          list={list}
          total={coupons.data?.total}
          loading={coupons.isLoading}
          error={coupons.error}
          onRetry={() => coupons.refetch()}
          searchPlaceholder="Search code or description…"
          empty={
            <div className="empty">
              <div className="empty-title">No coupons yet</div>
              <div className="muted">
                Create a code and it is immediately usable in the storefront checkout.
              </div>
              {canManage ? (
                <div style={{ marginTop: 10 }}>
                  <Button onClick={openCreate}>New coupon</Button>
                </div>
              ) : null}
            </div>
          }
        />
      </Card>

      <CrudFormModal
        open={modalOpen}
        title={editing ? `Edit ${editing.code}` : "New coupon"}
        form={form}
        fields={fields}
        onClose={() => setModalOpen(false)}
        onSubmit={form.submit}
        submitting={createCoupon.isPending || updateCoupon.isPending}
        error={mutationError}
        wide
        submitLabel={editing ? "Save" : "Create"}
      />
    </>
  );
}
