import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Modal,
  PageHeader,
  StatusBadge,
  Tabs,
  Textarea,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate, formatMoney, formatQty } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { productsQueryOptions } from "../catalog/queries";
import {
  EMPTY_INVOICE_LINE,
  creditNoteFormSchema,
  invoiceFormSchema,
  INVOICE_STATUSES,
  type CreditNote,
  type CreditNoteFormInput,
  type Invoice,
  type InvoiceFormInput,
  type InvoiceLine,
  type InvoiceLineFormInput,
} from "./schemas";
import {
  arAgingQueryOptions,
  creditNotesQueryOptions,
  customersQueryOptions,
  invoiceLinesQueryOptions,
  invoicesQueryOptions,
  locationsQueryOptions,
  taxRatesQueryOptions,
  useCreateCreditNote,
  useCreateInvoice,
  usePostInvoice,
  useReverseInvoice,
} from "./queries";

type Tab = "invoices" | "credit-notes" | "ar-aging";

const TABS: { key: Tab; label: string }[] = [
  { key: "invoices", label: "Invoices" },
  { key: "credit-notes", label: "Credit notes" },
  { key: "ar-aging", label: "AR aging" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyInvoiceForm(): InvoiceFormInput {
  return {
    customer_id: "",
    invoice_date: today(),
    currency: "INR",
    shipping_total: "0",
    due_date: "",
    notes: "",
    order_id: null,
    post: true,
    lines: [{ ...EMPTY_INVOICE_LINE }],
  };
}

function emptyCreditForm(): CreditNoteFormInput {
  return {
    invoice_id: "",
    note_date: today(),
    reason: "",
    restock: false,
    restock_location_id: null,
    lines: [],
  };
}

export function InvoicesPage() {
  const { has } = usePermissions();
  const canManage = has("invoicing.manage");

  const [tab, setTab] = useState<Tab>("invoices");
  const [status, setStatus] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<InvoiceFormInput>(emptyInvoiceForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<Invoice | null>(null);

  const [creditOpen, setCreditOpen] = useState(false);
  const [creditForm, setCreditForm] = useState<CreditNoteFormInput>(emptyCreditForm);
  const [creditErrors, setCreditErrors] = useState<Record<string, string>>({});

  const [asOf, setAsOf] = useState(today());

  const customers = useQuery(customersQueryOptions());
  const products = useQuery(productsQueryOptions());
  const taxRates = useQuery(taxRatesQueryOptions());
  const locations = useQuery(locationsQueryOptions());

  const invoices = useQuery(
    invoicesQueryOptions({ status: status ?? undefined, customerId: customerId ?? undefined }),
  );
  const creditNotes = useQuery(creditNotesQueryOptions());
  const aging = useQuery(arAgingQueryOptions(asOf));
  const detailLines = useQuery(invoiceLinesQueryOptions(detail?.id ?? ""));
  const creditSourceLines = useQuery(invoiceLinesQueryOptions(creditForm.invoice_id));

  const createInvoice = useCreateInvoice();
  const postInvoice = usePostInvoice();
  const reverseInvoice = useReverseInvoice();
  const createCreditNote = useCreateCreditNote();

  const customerOptions = useMemo(
    () => (customers.data ?? []).map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })),
    [customers.data],
  );
  const productOptions = useMemo(
    () =>
      (products.data?.items ?? []).map((p) => ({
        value: p.id,
        label: `${p.sku} — ${p.name}`,
        hint: formatMoney(p.base_price),
      })),
    [products.data],
  );
  const taxOptions = useMemo(
    () =>
      (taxRates.data ?? []).map((t) => ({
        value: t.id,
        label: `${t.code} — ${formatQty(t.percentage)}%`,
      })),
    [taxRates.data],
  );
  const locationOptions = useMemo(
    () => (locations.data ?? []).map((l) => ({ value: l.id, label: `${l.code} — ${l.name}` })),
    [locations.data],
  );
  const postedInvoiceOptions = useMemo(
    () =>
      (invoices.data ?? [])
        .filter((i) => i.status === "posted")
        .map((i) => ({ value: i.id, label: `${i.doc_number} — ${i.customer_name}` })),
    [invoices.data],
  );

  const customerName = (id: string) => customers.data?.find((c) => c.id === id)?.name ?? id;

  // Seed credit-note lines from the selected invoice's lines.
  useEffect(() => {
    const lines = creditSourceLines.data;
    if (!lines || !creditForm.invoice_id) return;
    setCreditForm((prev) =>
      prev.invoice_id !== creditForm.invoice_id
        ? prev
        : {
            ...prev,
            lines: lines.map((line) => ({
              invoice_line_id: line.id,
              description: line.description_snapshot,
              qty: line.qty,
              unit_price: line.unit_price,
              tax_amount: line.tax_amount,
            })),
          },
    );
  }, [creditSourceLines.data, creditForm.invoice_id]);

  function setField<K extends keyof InvoiceFormInput>(key: K, value: InvoiceFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setLine(index: number, patch: Partial<InvoiceLineFormInput>) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function chooseProduct(index: number, productId: string) {
    const product = (products.data?.items ?? []).find((p) => p.id === productId);
    const patch: Partial<InvoiceLineFormInput> = { product_id: productId };
    if (product) {
      patch.description = product.name;
      if (Number(product.base_price) > 0) patch.unit_price = product.base_price;
    }
    setLine(index, patch);
  }

  function chooseTax(index: number, taxRateId: string) {
    const rate = (taxRates.data ?? []).find((t) => t.id === taxRateId);
    setLine(index, { tax_rate_id: taxRateId, tax_percentage: rate ? rate.percentage : "0" });
  }

  function addLine() {
    setForm((prev) => ({ ...prev, lines: [...prev.lines, { ...EMPTY_INVOICE_LINE }] }));
  }

  function removeLine(index: number) {
    setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }));
  }

  function submitInvoice() {
    const parsed = invoiceFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createInvoice.mutate(parsed.data, {
      onSuccess: () => {
        setCreateOpen(false);
        setForm(emptyInvoiceForm());
      },
    });
  }

  function submitCreditNote() {
    const parsed = creditNoteFormSchema.safeParse(creditForm);
    if (!parsed.success) {
      setCreditErrors(fieldErrors(parsed.error));
      return;
    }
    setCreditErrors({});
    createCreditNote.mutate(parsed.data, {
      onSuccess: () => {
        setCreditOpen(false);
        setCreditForm(emptyCreditForm());
      },
    });
  }

  const invoiceColumns: Column<Invoice>[] = [
    { key: "doc", header: "Doc #", render: (i) => <strong>{i.doc_number}</strong> },
    { key: "customer", header: "Customer", render: (i) => i.customer_name },
    { key: "date", header: "Date", render: (i) => formatDate(i.invoice_date) },
    { key: "due", header: "Due", render: (i) => formatDate(i.due_date) },
    { key: "status", header: "Status", render: (i) => <StatusBadge status={i.status} /> },
    { key: "total", header: "Total", align: "right", render: (i) => formatMoney(i.total, i.currency) },
    {
      key: "actions",
      header: "",
      render: (i) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setDetail(i)}>
            View
          </Button>
          {canManage && i.status === "draft" ? (
            <Button onClick={() => postInvoice.mutate(i.id)} disabled={postInvoice.isPending}>
              Post
            </Button>
          ) : null}
          {canManage && i.status === "posted" ? (
            <Button
              variant="danger"
              onClick={() => reverseInvoice.mutate(i.id)}
              disabled={reverseInvoice.isPending}
            >
              Reverse
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  const lineColumns: Column<InvoiceLine>[] = [
    { key: "sku", header: "SKU", render: (l) => l.sku_snapshot || "—" },
    { key: "desc", header: "Description", render: (l) => l.description_snapshot },
    { key: "qty", header: "Qty", align: "right", render: (l) => formatQty(l.qty) },
    { key: "price", header: "Unit price", align: "right", render: (l) => formatMoney(l.unit_price) },
    { key: "tax", header: "Tax %", align: "right", render: (l) => formatQty(l.tax_percentage) },
    { key: "total", header: "Line total", align: "right", render: (l) => formatMoney(l.line_total) },
  ];

  const creditColumns: Column<CreditNote>[] = [
    { key: "doc", header: "Doc #", render: (c) => <strong>{c.doc_number}</strong> },
    { key: "customer", header: "Customer", render: (c) => customerName(c.customer_id) },
    { key: "date", header: "Date", render: (c) => formatDate(c.note_date) },
    { key: "status", header: "Status", render: (c) => <StatusBadge status={c.status} /> },
    { key: "total", header: "Total", align: "right", render: (c) => formatMoney(c.total) },
    { key: "reason", header: "Reason", render: (c) => c.reason ?? "—" },
  ];

  const agingRows = useMemo(
    () =>
      Object.entries(aging.data ?? {}).map(([id, bucket]) => ({
        customerId: id,
        ...bucket,
        total: String(
          Number(bucket.current) +
            Number(bucket.d30) +
            Number(bucket.d60) +
            Number(bucket.d90) +
            Number(bucket.older),
        ),
      })),
    [aging.data],
  );

  const agingColumns: Column<(typeof agingRows)[number]>[] = [
    { key: "customer", header: "Customer", render: (r) => customerName(r.customerId) },
    { key: "current", header: "Current", align: "right", render: (r) => formatMoney(r.current) },
    { key: "d30", header: "1–30", align: "right", render: (r) => formatMoney(r.d30) },
    { key: "d60", header: "31–60", align: "right", render: (r) => formatMoney(r.d60) },
    { key: "d90", header: "61–90", align: "right", render: (r) => formatMoney(r.d90) },
    { key: "older", header: "90+", align: "right", render: (r) => formatMoney(r.older) },
    { key: "total", header: "Outstanding", align: "right", render: (r) => formatMoney(r.total) },
  ];

  return (
    <>
      <PageHeader
        title="Invoicing"
        description="Customer invoices, credit notes and receivables aging"
      />

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "invoices" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="Status">
                <SheetSelect
                  value={status}
                  options={INVOICE_STATUSES.map((s) => ({ value: s, label: s }))}
                  onChange={setStatus}
                  placeholder="All statuses"
                />
              </Field>
              <Field label="Customer">
                <SheetSelect
                  value={customerId}
                  options={customerOptions}
                  onChange={setCustomerId}
                  placeholder="All customers"
                  loading={customers.isLoading}
                />
              </Field>
              <div className="toolbar">
                {canManage ? (
                  <Button onClick={() => setCreateOpen(true)}>New invoice</Button>
                ) : null}
              </div>
            </div>
          </Card>

          <ErrorBanner error={postInvoice.error ?? reverseInvoice.error} />

          <Card>
            <DataTable
              columns={invoiceColumns}
              rows={invoices.data}
              rowKey={(i) => i.id}
              loading={invoices.isLoading}
              error={invoices.error}
              onRetry={() => invoices.refetch()}
              empty={<EmptyState title="No invoices" message="Create your first invoice." />}
            />
          </Card>
        </>
      ) : null}

      {tab === "credit-notes" ? (
        <>
          <Card
            title="Credit notes"
            actions={
              canManage ? (
                <Button onClick={() => setCreditOpen(true)} disabled={postedInvoiceOptions.length === 0}>
                  New credit note
                </Button>
              ) : null
            }
          >
            <DataTable
              columns={creditColumns}
              rows={creditNotes.data}
              rowKey={(c) => c.id}
              loading={creditNotes.isLoading}
              error={creditNotes.error}
              onRetry={() => creditNotes.refetch()}
              empty={<EmptyState title="No credit notes" message="Issue a credit against a posted invoice." />}
            />
          </Card>
        </>
      ) : null}

      {tab === "ar-aging" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="As of">
                <Input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
              </Field>
            </div>
          </Card>
          <Card title="Accounts receivable aging">
            <DataTable
              columns={agingColumns}
              rows={agingRows}
              rowKey={(r) => r.customerId}
              loading={aging.isLoading}
              error={aging.error}
              onRetry={() => aging.refetch()}
              empty={<EmptyState title="Nothing outstanding" message="No open receivables at this date." />}
            />
          </Card>
        </>
      ) : null}

      <Modal
        open={createOpen}
        title="New invoice"
        onClose={() => setCreateOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitInvoice} disabled={createInvoice.isPending}>
              {createInvoice.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createInvoice.error} />
        <div className="grid-2">
          <Field label="Customer" error={errors.customer_id}>
            <SheetSelect
              value={form.customer_id || null}
              options={customerOptions}
              onChange={(value) => setField("customer_id", value)}
              loading={customers.isLoading}
            />
          </Field>
          <Field label="Invoice date" error={errors.invoice_date}>
            <Input
              type="date"
              value={form.invoice_date}
              onChange={(event) => setField("invoice_date", event.target.value)}
            />
          </Field>
        </div>
        <div className="grid-3">
          <Field label="Currency" error={errors.currency}>
            <Input
              value={form.currency}
              maxLength={3}
              onChange={(event) => setField("currency", event.target.value.toUpperCase())}
            />
          </Field>
          <Field label="Due date" error={errors.due_date}>
            <Input
              type="date"
              value={form.due_date ?? ""}
              onChange={(event) => setField("due_date", event.target.value)}
            />
          </Field>
          <Field label="Shipping" error={errors.shipping_total}>
            <Input
              value={form.shipping_total}
              onChange={(event) => setField("shipping_total", event.target.value)}
            />
          </Field>
        </div>
        <Field label="Notes" error={errors.notes}>
          <Textarea
            rows={2}
            value={form.notes ?? ""}
            onChange={(event) => setField("notes", event.target.value)}
          />
        </Field>

        <div className="card-head" style={{ marginTop: 8 }}>
          <div className="card-title">Lines</div>
          <Button variant="secondary" onClick={addLine}>
            Add line
          </Button>
        </div>
        {errors.lines ? <div className="error-text">{errors.lines}</div> : null}
        {form.lines.map((line, index) => (
          <div key={index} className="grid-3" style={{ alignItems: "end", marginBottom: 8 }}>
            <Field label="Product" error={errors[`lines.${index}.product_id`]}>
              <SheetSelect
                value={line.product_id ?? null}
                options={productOptions}
                onChange={(value) => chooseProduct(index, value)}
                loading={products.isLoading}
              />
            </Field>
            <Field label="Description" error={errors[`lines.${index}.description`]}>
              <Input
                value={line.description ?? ""}
                onChange={(event) => setLine(index, { description: event.target.value })}
              />
            </Field>
            <Field label="Qty" error={errors[`lines.${index}.qty`]}>
              <Input value={line.qty} onChange={(event) => setLine(index, { qty: event.target.value })} />
            </Field>
            <Field label="Unit price" error={errors[`lines.${index}.unit_price`]}>
              <Input
                value={line.unit_price}
                onChange={(event) => setLine(index, { unit_price: event.target.value })}
              />
            </Field>
            <Field label="Discount" error={errors[`lines.${index}.discount`]}>
              <Input
                value={line.discount}
                onChange={(event) => setLine(index, { discount: event.target.value })}
              />
            </Field>
            <Field label="Tax rate" error={errors[`lines.${index}.tax_rate_id`]}>
              <SheetSelect
                value={line.tax_rate_id ?? null}
                options={taxOptions}
                onChange={(value) => chooseTax(index, value)}
                placeholder="No tax"
                loading={taxRates.isLoading}
                emptyText="No tax rates"
              />
            </Field>
            <div className="toolbar">
              <Button variant="danger" onClick={() => removeLine(index)} disabled={form.lines.length === 1}>
                Remove
              </Button>
            </div>
          </div>
        ))}

        <label className="pill">
          <input
            type="checkbox"
            checked={form.post}
            onChange={(event) => setField("post", event.target.checked)}
          />
          Post immediately
        </label>
      </Modal>

      <Sheet
        open={detail !== null}
        title={detail ? `Invoice ${detail.doc_number}` : "Invoice"}
        onClose={() => setDetail(null)}
      >
        {detail ? (
          <div style={{ padding: 18 }}>
            <div className="grid-2">
              <div>
                <div className="muted">Customer</div>
                <div>{detail.customer_name}</div>
              </div>
              <div>
                <div className="muted">Status</div>
                <div>
                  <StatusBadge status={detail.status} />
                </div>
              </div>
              <div>
                <div className="muted">Date</div>
                <div>{formatDate(detail.invoice_date)}</div>
              </div>
              <div>
                <div className="muted">Due</div>
                <div>{formatDate(detail.due_date)}</div>
              </div>
              <div>
                <div className="muted">Subtotal</div>
                <div>{formatMoney(detail.subtotal, detail.currency)}</div>
              </div>
              <div>
                <div className="muted">Tax</div>
                <div>{formatMoney(detail.tax_total, detail.currency)}</div>
              </div>
              <div>
                <div className="muted">Shipping</div>
                <div>{formatMoney(detail.shipping_total, detail.currency)}</div>
              </div>
              <div>
                <div className="muted">Total</div>
                <div>
                  <strong>{formatMoney(detail.total, detail.currency)}</strong>
                </div>
              </div>
            </div>
            <h3 className="card-title" style={{ marginTop: 18 }}>
              Lines
            </h3>
            <DataTable
              columns={lineColumns}
              rows={detailLines.data}
              rowKey={(l) => l.id}
              loading={detailLines.isLoading}
              error={detailLines.error}
              onRetry={() => detailLines.refetch()}
            />
          </div>
        ) : null}
      </Sheet>

      <Modal
        open={creditOpen}
        title="New credit note"
        onClose={() => setCreditOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreditNote} disabled={createCreditNote.isPending}>
              {createCreditNote.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createCreditNote.error} />
        <div className="grid-2">
          <Field label="Invoice" error={creditErrors.invoice_id}>
            <SheetSelect
              value={creditForm.invoice_id || null}
              options={postedInvoiceOptions}
              onChange={(value) =>
                setCreditForm((prev) => ({ ...prev, invoice_id: value, lines: [] }))
              }
              placeholder="Select a posted invoice"
              loading={invoices.isLoading}
            />
          </Field>
          <Field label="Note date" error={creditErrors.note_date}>
            <Input
              type="date"
              value={creditForm.note_date}
              onChange={(event) =>
                setCreditForm((prev) => ({ ...prev, note_date: event.target.value }))
              }
            />
          </Field>
        </div>
        <Field label="Reason" error={creditErrors.reason}>
          <Textarea
            rows={2}
            value={creditForm.reason ?? ""}
            onChange={(event) => setCreditForm((prev) => ({ ...prev, reason: event.target.value }))}
          />
        </Field>

        <div className="toolbar" style={{ marginBottom: 8 }}>
          <label className="pill">
            <input
              type="checkbox"
              checked={creditForm.restock}
              onChange={(event) =>
                setCreditForm((prev) => ({ ...prev, restock: event.target.checked }))
              }
            />
            Restock returned goods
          </label>
        </div>
        {creditForm.restock ? (
          <Field label="Restock location" error={creditErrors.restock_location_id}>
            <SheetSelect
              value={creditForm.restock_location_id}
              options={locationOptions}
              onChange={(value) =>
                setCreditForm((prev) => ({ ...prev, restock_location_id: value }))
              }
              loading={locations.isLoading}
            />
          </Field>
        ) : null}

        <div className="card-head" style={{ marginTop: 8 }}>
          <div className="card-title">Lines from invoice</div>
        </div>
        {creditSourceLines.isLoading && creditForm.invoice_id ? <div className="muted">Loading lines…</div> : null}
        {!creditForm.invoice_id ? (
          <div className="muted">Select an invoice to load its lines.</div>
        ) : null}
        {creditForm.lines.map((line, index) => (
          <div key={line.invoice_line_id ?? index} className="grid-2" style={{ alignItems: "end" }}>
            <Field label="Description">
              <Input
                value={line.description ?? ""}
                onChange={(event) =>
                  setCreditForm((prev) => ({
                    ...prev,
                    lines: prev.lines.map((l, i) =>
                      i === index ? { ...l, description: event.target.value } : l,
                    ),
                  }))
                }
              />
            </Field>
            <Field label="Qty" error={creditErrors[`lines.${index}.qty`]}>
              <Input
                value={line.qty}
                onChange={(event) =>
                  setCreditForm((prev) => ({
                    ...prev,
                    lines: prev.lines.map((l, i) =>
                      i === index ? { ...l, qty: event.target.value } : l,
                    ),
                  }))
                }
              />
            </Field>
          </div>
        ))}
        {creditErrors.lines ? <div className="error-text">{creditErrors.lines}</div> : null}
      </Modal>
    </>
  );
}
