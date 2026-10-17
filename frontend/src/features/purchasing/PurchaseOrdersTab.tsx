import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { isStockableType } from "../../lib/location-types";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Modal,
  StatusBadge,
  Textarea,
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate, formatMoney, formatQty } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  locationOptionsQueryOptions,
  productOptionsQueryOptions,
  purchaseOrderLinesQueryOptions,
  purchaseOrdersQueryOptions,
  useCreatePurchaseOrder,
  usePurchaseOrderAction,
  useReceiveGoods,
  vendorsQueryOptions,
} from "./queries";
import {
  CURRENCIES,
  PO_STATUSES,
  poFormSchema,
  receiveFormSchema,
  type GoodsReceipt,
  type PoFormInput,
  type PoLineForm,
  type PurchaseOrder,
  type PurchaseOrderLine,
  type ReceiveLinePayload,
} from "./schemas";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyLine(): PoLineForm {
  return {
    product_id: "",
    ordered_qty: "1",
    unit_cost: "0",
    uom_id: null,
    tax_rate_id: null,
    notes: "",
  };
}

function emptyForm(): PoFormInput {
  return {
    vendor_id: "",
    order_date: today(),
    expected_date: "",
    currency: "USD",
    notes: "",
    lines: [emptyLine()],
  };
}

interface ReceiveDraft {
  order_line_id: string;
  product_id: string;
  remaining: string;
  qty_received: string;
  batch_ref: string;
  serials: string;
}

export function PurchaseOrdersTab() {
  const { has } = usePermissions();
  const canCreate = has("purchasing.po.create");
  const canApprove = has("purchasing.po.approve");
  const canReceive = has("purchasing.bill.manage");

  const [status, setStatus] = useState<string | null>(null);
  const orders = useQuery(purchaseOrdersQueryOptions(status ?? undefined));
  const vendors = useQuery(vendorsQueryOptions());
  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());

  const createPo = useCreatePurchaseOrder();
  const poAction = usePurchaseOrderAction();
  const receiveGoods = useReceiveGoods();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<PoFormInput>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [linesOrder, setLinesOrder] = useState<PurchaseOrder | null>(null);
  const orderLines = useQuery(purchaseOrderLinesQueryOptions(linesOrder?.id ?? ""));

  const [receiveOrder, setReceiveOrder] = useState<PurchaseOrder | null>(null);
  const receiveLines = useQuery(purchaseOrderLinesQueryOptions(receiveOrder?.id ?? ""));
  const [receiveLocation, setReceiveLocation] = useState("");
  const [receiveDraft, setReceiveDraft] = useState<ReceiveDraft[]>([]);
  const [receiveErrors, setReceiveErrors] = useState<Record<string, string>>({});
  const [receipt, setReceipt] = useState<GoodsReceipt | null>(null);

  const vendorName = useMemo(() => {
    const map = new Map<string, string>();
    for (const vendor of vendors.data ?? []) map.set(vendor.id, vendor.name);
    return map;
  }, [vendors.data]);

  const productName = useMemo(() => {
    const map = new Map<string, string>();
    for (const product of products.data ?? []) map.set(product.id, `${product.sku} — ${product.name}`);
    return map;
  }, [products.data]);

  const serialTracked = useMemo(() => {
    const set = new Set<string>();
    for (const product of products.data ?? []) {
      if (product.track_serials) set.add(product.id);
    }
    return set;
  }, [products.data]);

  const vendorOptions = useMemo(
    () => (vendors.data ?? []).map((v) => ({ value: v.id, label: v.name, hint: v.code })),
    [vendors.data],
  );
  const productSelectOptions = useMemo(
    () =>
      (products.data ?? [])
        .filter((p) => p.is_purchasable !== false)
        .map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}`, hint: p.base_cost })),
    [products.data],
  );
  const binOptions = useMemo(
    () =>
      (locations.data ?? [])
        .filter((l) => isStockableType(l.location_type))
        .map((l) => ({ value: l.id, label: `${l.code} — ${l.name}` })),
    [locations.data],
  );

  useEffect(() => {
    if (!receiveOrder || !receiveLines.data) return;
    setReceiveDraft(
      receiveLines.data.map((line) => {
        const remaining = String(
          Math.max(0, Number(line.ordered_qty) - Number(line.received_qty)),
        );
        return {
          order_line_id: line.id,
          product_id: line.product_id,
          remaining,
          qty_received: remaining,
          batch_ref: "",
          serials: "",
        };
      }),
    );
  }, [receiveOrder, receiveLines.data]);

  function setField<K extends keyof PoFormInput>(key: K, value: PoFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setLine(index: number, patch: Partial<PoLineForm>) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function pickProduct(index: number, productId: string) {
    const product = (products.data ?? []).find((p) => p.id === productId);
    setLine(index, {
      product_id: productId,
      uom_id: product?.uom_id ?? null,
      tax_rate_id: product?.default_tax_rate_id ?? null,
      unit_cost:
        product && Number(form.lines[index]?.unit_cost ?? "0") === 0
          ? product.base_cost
          : (form.lines[index]?.unit_cost ?? "0"),
    });
  }

  function submit() {
    const parsed = poFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    const notes = parsed.data.notes?.trim() ? parsed.data.notes : undefined;
    createPo.mutate(
      {
        vendor_id: parsed.data.vendor_id,
        order_date: parsed.data.order_date,
        expected_date: parsed.data.expected_date ? parsed.data.expected_date : null,
        currency: parsed.data.currency.toUpperCase(),
        notes,
        lines: parsed.data.lines.map((line) => ({
          product_id: line.product_id,
          ordered_qty: line.ordered_qty,
          unit_cost: line.unit_cost,
          uom_id: line.uom_id,
          tax_rate_id: line.tax_rate_id,
          notes: line.notes?.trim() ? line.notes : undefined,
        })),
      },
      {
        onSuccess: () => {
          setOpen(false);
          setForm(emptyForm());
        },
      },
    );
  }

  function openReceive(order: PurchaseOrder) {
    setReceiveOrder(order);
    setReceipt(null);
    setReceiveLocation("");
    setReceiveErrors({});
  }

  function submitReceive() {
    if (!receiveOrder) return;
    const invalid = receiveDraft.find(
      (line) => !/^\d+(\.\d+)?$/.test(line.qty_received.trim()),
    );
    if (invalid) {
      setReceiveErrors({ "lines.qty_received": "Enter a valid quantity" });
      return;
    }
    const parseSerials = (value: string) =>
      value
        .split(/[\n,;]+/)
        .map((s) => s.trim())
        .filter(Boolean);
    const candidate = {
      location_id: receiveLocation,
      lines: receiveDraft
        .filter((line) => Number(line.qty_received) > 0)
        .map((line) => ({
          order_line_id: line.order_line_id,
          qty_received: line.qty_received,
          batch_ref: line.batch_ref,
          serials: line.serials,
        })),
    };
    const parsed = receiveFormSchema.safeParse(candidate);
    if (!parsed.success) {
      setReceiveErrors(fieldErrors(parsed.error));
      return;
    }
    const errors: Record<string, string> = {};
    const productIdByLine = new Map(receiveDraft.map((d) => [d.order_line_id, d.product_id]));
    parsed.data.lines.forEach((line, index) => {
      if (!serialTracked.has(productIdByLine.get(line.order_line_id) ?? "")) return;
      const serials = parseSerials(line.serials ?? "");
      if (serials.length !== Number(line.qty_received)) {
        errors[`lines.${index}.serials`] =
          `Enter ${line.qty_received} serial number(s) — one per unit`;
      }
    });
    if (Object.keys(errors).length > 0) {
      setReceiveErrors(errors);
      return;
    }
    setReceiveErrors({});
    const lines: ReceiveLinePayload[] = parsed.data.lines.map((line) => {
      const serials = parseSerials(line.serials ?? "");
      return {
        order_line_id: line.order_line_id,
        qty_received: line.qty_received,
        location_id: parsed.data.location_id,
        batch_ref: line.batch_ref?.trim() ? line.batch_ref : undefined,
        serials: serials.length > 0 ? serials : undefined,
      };
    });
    receiveGoods.mutate(
      { id: receiveOrder.id, lines },
      { onSuccess: (posted) => setReceipt(posted) },
    );
  }

  const columns: Column<PurchaseOrder>[] = [
    { key: "doc", header: "PO", render: (o) => <strong>{o.doc_number}</strong> },
    { key: "vendor", header: "Vendor", render: (o) => vendorName.get(o.vendor_id) ?? o.vendor_id },
    { key: "status", header: "Status", render: (o) => <StatusBadge status={o.status} /> },
    { key: "order_date", header: "Ordered", render: (o) => formatDate(o.order_date) },
    { key: "expected", header: "Expected", render: (o) => formatDate(o.expected_date) },
    { key: "received", header: "Received qty", align: "right", render: (o) => formatQty(o.received_qty) },
    { key: "currency", header: "Currency", render: (o) => o.currency },
    {
      key: "actions",
      header: "",
      render: (o) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setLinesOrder(o)}>
            Lines
          </Button>
          {canCreate && o.status === "draft" ? (
            <Button onClick={() => poAction.mutate({ id: o.id, action: "submit" })}>Submit</Button>
          ) : null}
          {canApprove && o.status === "submitted" ? (
            <Button onClick={() => poAction.mutate({ id: o.id, action: "approve" })}>Approve</Button>
          ) : null}
          {canReceive && (o.status === "approved" || o.status === "partially_received") ? (
            <Button onClick={() => openReceive(o)}>Receive</Button>
          ) : null}
          {canApprove && ["draft", "submitted", "approved"].includes(o.status) ? (
            <Button variant="danger" onClick={() => poAction.mutate({ id: o.id, action: "cancel" })}>
              Cancel
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  const lineColumns: Column<PurchaseOrderLine>[] = [
    { key: "product", header: "Product", render: (l) => productName.get(l.product_id) ?? l.product_id },
    { key: "ordered", header: "Ordered", align: "right", render: (l) => formatQty(l.ordered_qty) },
    { key: "received", header: "Received", align: "right", render: (l) => formatQty(l.received_qty) },
    { key: "cost", header: "Unit cost", align: "right", render: (l) => formatMoney(l.unit_cost) },
  ];

  return (
    <>
      <Card>
        <div className="form-row">
          <Field label="Status">
            <SheetSelect
              value={status}
              options={[
                { value: "", label: "All statuses" },
                ...PO_STATUSES.map((s) => ({ value: s, label: s.replace(/_/g, " ") })),
              ]}
              onChange={(value) => setStatus(value || null)}
              placeholder="All statuses"
            />
          </Field>
          <div className="toolbar" style={{ alignItems: "flex-end" }}>
            {canCreate ? <Button onClick={() => setOpen(true)}>New PO</Button> : null}
          </div>
        </div>
        <ErrorBanner error={poAction.error} />
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={orders.data}
          rowKey={(o) => o.id}
          loading={orders.isLoading}
          error={orders.error}
          onRetry={() => orders.refetch()}
          empty={<EmptyState title="No purchase orders" message="Create your first purchase order." />}
        />
      </Card>

      <Modal
        open={open}
        title="New purchase order"
        onClose={() => setOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createPo.isPending}>
              {createPo.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createPo.error} />
        <div className="grid-3">
          <Field label="Vendor" error={errors.vendor_id}>
            <SheetSelect
              value={form.vendor_id || null}
              options={vendorOptions}
              onChange={(value) => setField("vendor_id", value)}
              loading={vendors.isLoading}
            />
          </Field>
          <Field label="Order date" error={errors.order_date}>
            <Input
              value={form.order_date}
              placeholder="YYYY-MM-DD"
              onChange={(event) => setField("order_date", event.target.value)}
            />
          </Field>
          <Field label="Expected date" error={errors.expected_date}>
            <Input
              value={form.expected_date ?? ""}
              placeholder="YYYY-MM-DD"
              onChange={(event) => setField("expected_date", event.target.value)}
            />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Currency" error={errors.currency}>
            <SheetSelect
              value={form.currency}
              options={CURRENCIES.map((c) => ({ value: c, label: c }))}
              onChange={(value) => setField("currency", value)}
            />
          </Field>
          <Field label="Notes" error={errors.notes}>
            <Textarea
              rows={2}
              value={form.notes ?? ""}
              onChange={(event) => setField("notes", event.target.value)}
            />
          </Field>
        </div>

        <div className="card-head">
          <div className="card-title">Lines</div>
          <div className="toolbar">
            <Button
              variant="secondary"
              onClick={() => setForm((prev) => ({ ...prev, lines: [...prev.lines, emptyLine()] }))}
            >
              Add line
            </Button>
          </div>
        </div>
        {errors.lines ? <div className="error-text">{errors.lines}</div> : null}
        {form.lines.map((line, index) => (
          <div className="form-row" key={index}>
            <Field label="Product" error={errors[`lines.${index}.product_id`]}>
              <SheetSelect
                value={line.product_id || null}
                options={productSelectOptions}
                onChange={(value) => pickProduct(index, value)}
                loading={products.isLoading}
              />
            </Field>
            <Field label="Qty" error={errors[`lines.${index}.ordered_qty`]}>
              <Input
                value={line.ordered_qty}
                onChange={(event) => setLine(index, { ordered_qty: event.target.value })}
              />
            </Field>
            <Field label="Unit cost" error={errors[`lines.${index}.unit_cost`]}>
              <Input
                value={line.unit_cost}
                onChange={(event) => setLine(index, { unit_cost: event.target.value })}
              />
            </Field>
            <Button
              variant="secondary"
              disabled={form.lines.length <= 1}
              onClick={() =>
                setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }))
              }
            >
              Remove
            </Button>
          </div>
        ))}
      </Modal>

      <Modal
        open={linesOrder !== null}
        title={linesOrder ? `Lines — ${linesOrder.doc_number}` : "Lines"}
        onClose={() => setLinesOrder(null)}
        wide
      >
        <DataTable
          columns={lineColumns}
          rows={orderLines.data}
          rowKey={(l) => l.id}
          loading={orderLines.isLoading}
          error={orderLines.error}
          onRetry={() => orderLines.refetch()}
          empty={<EmptyState title="No lines" />}
        />
      </Modal>

      <Modal
        open={receiveOrder !== null}
        title={receiveOrder ? `Receive — ${receiveOrder.doc_number}` : "Receive"}
        onClose={() => setReceiveOrder(null)}
        wide
        footer={
          receipt ? (
            <Button variant="secondary" onClick={() => setReceiveOrder(null)}>
              Close
            </Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setReceiveOrder(null)}>
                Cancel
              </Button>
              <Button onClick={submitReceive} disabled={receiveGoods.isPending}>
                {receiveGoods.isPending ? "Receiving…" : "Post receipt"}
              </Button>
            </>
          )
        }
      >
        <ErrorBanner error={receiveGoods.error} />
        {receipt ? (
          <div>
            <p>
              Receipt <strong>{receipt.doc_number}</strong> posted. Use its id when creating a
              vendor bill from a receipt:
            </p>
            <p className="muted">{receipt.id}</p>
          </div>
        ) : (
          <>
            <Field label="Receive to location (bin)" error={receiveErrors.location_id}>
              <SheetSelect
                value={receiveLocation || null}
                options={binOptions}
                onChange={setReceiveLocation}
                loading={locations.isLoading}
                emptyText="No bin locations"
              />
            </Field>
            {receiveErrors["lines"] ? (
              <div className="error-text">{receiveErrors["lines"]}</div>
            ) : null}
            {receiveErrors["lines.qty_received"] ? (
              <div className="error-text">{receiveErrors["lines.qty_received"]}</div>
            ) : null}
            {receiveDraft.map((line, index) => (
              <div className="form-row" key={line.order_line_id}>
                <Field
                  label={productName.get(line.product_id) ?? line.product_id}
                  hint={`Remaining ${formatQty(line.remaining)}`}
                >
                  <div className="muted">{line.remaining}</div>
                </Field>
                <Field label="Qty received" error={receiveErrors[`lines.${index}.qty_received`]}>
                  <Input
                    value={line.qty_received}
                    onChange={(event) =>
                      setReceiveDraft((prev) =>
                        prev.map((draft, i) =>
                          i === index ? { ...draft, qty_received: event.target.value } : draft,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Batch ref">
                  <Input
                    value={line.batch_ref}
                    onChange={(event) =>
                      setReceiveDraft((prev) =>
                        prev.map((draft, i) =>
                          i === index ? { ...draft, batch_ref: event.target.value } : draft,
                        ),
                      )
                    }
                  />
                </Field>
                {serialTracked.has(line.product_id) ? (
                  <Field
                    label="Serial numbers"
                    hint="One per unit — separate with commas or new lines"
                    error={receiveErrors[`lines.${index}.serials`]}
                  >
                    <Input
                      value={line.serials}
                      placeholder="SN-001, SN-002"
                      onChange={(event) =>
                        setReceiveDraft((prev) =>
                          prev.map((draft, i) =>
                            i === index ? { ...draft, serials: event.target.value } : draft,
                          ),
                        )
                      }
                    />
                  </Field>
                ) : null}
              </div>
            ))}
          </>
        )}
      </Modal>
    </>
  );
}
