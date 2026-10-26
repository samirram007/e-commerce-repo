import { useMemo, useState } from "react";
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
  StatusBadge,
  Tabs,
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate, formatMoney, formatQty } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  productOptionsQueryOptions,
  useCreateAdhocBill,
  useCreateBillFromReceipt,
  vendorBillLinesQueryOptions,
  vendorBillsQueryOptions,
  vendorsQueryOptions,
} from "./queries";
import {
  CURRENCIES,
  adhocBillFormSchema,
  billFromReceiptFormSchema,
  type AdhocBillFormInput,
  type BillLineForm,
  type BillFromReceiptFormInput,
  type VendorBill,
  type VendorBillLine,
} from "./schemas";

type BillMode = "receipt" | "adhoc";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyBillLine(): BillLineForm {
  return { product_id: null, description: "", qty: "1", unit_cost: "0", tax_percentage: "0" };
}

const EMPTY_ADHOC: AdhocBillFormInput = {
  vendor_id: "",
  bill_date: today(),
  currency: "INR",
  lines: [emptyBillLine()],
};

const EMPTY_RECEIPT: BillFromReceiptFormInput = {
  receipt_id: "",
  bill_date: today(),
  vendor_ref: "",
};

export function VendorBillsTab() {
  const { has } = usePermissions();
  const canManage = has("purchasing.bill.manage");

  const bills = useQuery(vendorBillsQueryOptions());
  const vendors = useQuery(vendorsQueryOptions());
  const products = useQuery(productOptionsQueryOptions());
  const createAdhoc = useCreateAdhocBill();
  const createFromReceipt = useCreateBillFromReceipt();

  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<BillMode>("receipt");
  const [adhoc, setAdhoc] = useState<AdhocBillFormInput>(EMPTY_ADHOC);
  const [receipt, setReceipt] = useState<BillFromReceiptFormInput>(EMPTY_RECEIPT);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [linesBill, setLinesBill] = useState<VendorBill | null>(null);
  const billLines = useQuery(vendorBillLinesQueryOptions(linesBill?.id ?? ""));

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

  const vendorOptions = useMemo(
    () => (vendors.data ?? []).map((v) => ({ value: v.id, label: v.name, hint: v.code })),
    [vendors.data],
  );
  const productOptions = useMemo(
    () =>
      (products.data ?? []).map((p) => ({
        value: p.id,
        label: `${p.sku} — ${p.name}`,
        hint: p.base_cost,
      })),
    [products.data],
  );

  function close() {
    setOpen(false);
    setErrors({});
  }

  function submitReceipt() {
    const parsed = billFromReceiptFormSchema.safeParse(receipt);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createFromReceipt.mutate(
      {
        receipt_id: parsed.data.receipt_id,
        bill_date: parsed.data.bill_date,
        vendor_ref: parsed.data.vendor_ref,
      },
      { onSuccess: close },
    );
  }

  function submitAdhoc() {
    const parsed = adhocBillFormSchema.safeParse(adhoc);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createAdhoc.mutate(
      {
        vendor_id: parsed.data.vendor_id,
        bill_date: parsed.data.bill_date,
        currency: parsed.data.currency.toUpperCase(),
        lines: parsed.data.lines.map((line) => ({
          product_id: line.product_id || null,
          description: line.description?.trim() ? line.description : undefined,
          qty: line.qty,
          unit_cost: line.unit_cost,
          tax_percentage: line.tax_percentage?.trim() ? line.tax_percentage : "0",
        })),
      },
      { onSuccess: close },
    );
  }

  function setBillLine(index: number, patch: Partial<BillLineForm>) {
    setAdhoc((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  const columns: Column<VendorBill>[] = [
    { key: "doc", header: "Bill", render: (b) => <strong>{b.doc_number}</strong> },
    { key: "vendor", header: "Vendor", render: (b) => vendorName.get(b.vendor_id) ?? b.vendor_id },
    { key: "status", header: "Status", render: (b) => <StatusBadge status={b.status} /> },
    { key: "bill_date", header: "Bill date", render: (b) => formatDate(b.bill_date) },
    { key: "due_date", header: "Due", render: (b) => formatDate(b.due_date) },
    { key: "total", header: "Total", align: "right", render: (b) => formatMoney(b.total, b.currency) },
    {
      key: "actions",
      header: "",
      render: (b) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setLinesBill(b)}>
            Lines
          </Button>
        </span>
      ),
    },
  ];

  const billLineColumns: Column<VendorBillLine>[] = [
    { key: "product", header: "Product", render: (l) => productName.get(l.product_id) ?? (l.product_id || "—") },
    { key: "qty", header: "Qty", align: "right", render: (l) => formatQty(l.qty) },
    { key: "cost", header: "Unit cost", align: "right", render: (l) => formatMoney(l.unit_cost) },
    { key: "total", header: "Line total", align: "right", render: (l) => formatMoney(l.line_total) },
    { key: "tax", header: "Tax", align: "right", render: (l) => formatMoney(l.tax_amount) },
  ];

  return (
    <>
      <Card>
        <div className="toolbar" style={{ justifyContent: "flex-end" }}>
          {canManage ? <Button onClick={() => setOpen(true)}>New bill</Button> : null}
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={bills.data}
          rowKey={(b) => b.id}
          loading={bills.isLoading}
          error={bills.error}
          onRetry={() => bills.refetch()}
          empty={<EmptyState title="No vendor bills" message="Bills appear here once posted." />}
        />
      </Card>

      <Modal
        open={open}
        title="New vendor bill"
        onClose={close}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button
              onClick={mode === "receipt" ? submitReceipt : submitAdhoc}
              disabled={createAdhoc.isPending || createFromReceipt.isPending}
            >
              {createAdhoc.isPending || createFromReceipt.isPending ? "Saving…" : "Create bill"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createAdhoc.error ?? createFromReceipt.error} />
        <Tabs
          tabs={[
            { key: "receipt", label: "From goods receipt" },
            { key: "adhoc", label: "Ad-hoc bill" },
          ]}
          active={mode}
          onChange={(key) => {
            setMode(key as BillMode);
            setErrors({});
          }}
        />

        {mode === "receipt" ? (
          <div>
            <Field label="Goods receipt id" error={errors.receipt_id}>
              <Input
                value={receipt.receipt_id}
                placeholder="Receipt id from a posted goods receipt"
                onChange={(event) => setReceipt((prev) => ({ ...prev, receipt_id: event.target.value }))}
              />
            </Field>
            <div className="grid-2">
              <Field label="Bill date" error={errors.bill_date}>
                <Input
                  value={receipt.bill_date}
                  placeholder="YYYY-MM-DD"
                  onChange={(event) => setReceipt((prev) => ({ ...prev, bill_date: event.target.value }))}
                />
              </Field>
              <Field label="Vendor reference" error={errors.vendor_ref}>
                <Input
                  value={receipt.vendor_ref ?? ""}
                  onChange={(event) => setReceipt((prev) => ({ ...prev, vendor_ref: event.target.value }))}
                />
              </Field>
            </div>
          </div>
        ) : (
          <div>
            <div className="grid-3">
              <Field label="Vendor" error={errors.vendor_id}>
                <SheetSelect
                  value={adhoc.vendor_id || null}
                  options={vendorOptions}
                  onChange={(value) => setAdhoc((prev) => ({ ...prev, vendor_id: value }))}
                  loading={vendors.isLoading}
                />
              </Field>
              <Field label="Bill date" error={errors.bill_date}>
                <Input
                  value={adhoc.bill_date}
                  placeholder="YYYY-MM-DD"
                  onChange={(event) => setAdhoc((prev) => ({ ...prev, bill_date: event.target.value }))}
                />
              </Field>
              <Field label="Currency" error={errors.currency}>
                <SheetSelect
                  value={adhoc.currency}
                  options={CURRENCIES.map((c) => ({ value: c, label: c }))}
                  onChange={(value) => setAdhoc((prev) => ({ ...prev, currency: value }))}
                />
              </Field>
            </div>

            <div className="card-head">
              <div className="card-title">Lines</div>
              <div className="toolbar">
                <Button
                  variant="secondary"
                  onClick={() =>
                    setAdhoc((prev) => ({ ...prev, lines: [...prev.lines, emptyBillLine()] }))
                  }
                >
                  Add line
                </Button>
              </div>
            </div>
            {errors.lines ? <div className="error-text">{errors.lines}</div> : null}
            {adhoc.lines.map((line, index) => (
              <div className="form-row" key={index}>
                <Field label="Product (optional)">
                  <SheetSelect
                    value={line.product_id}
                    options={[{ value: "", label: "No product" }, ...productOptions]}
                    onChange={(value) => setBillLine(index, { product_id: value || null })}
                    loading={products.isLoading}
                  />
                </Field>
                <Field label="Description">
                  <Input
                    value={line.description ?? ""}
                    onChange={(event) => setBillLine(index, { description: event.target.value })}
                  />
                </Field>
                <Field label="Qty" error={errors[`lines.${index}.qty`]}>
                  <Input
                    value={line.qty}
                    onChange={(event) => setBillLine(index, { qty: event.target.value })}
                  />
                </Field>
                <Field label="Unit cost" error={errors[`lines.${index}.unit_cost`]}>
                  <Input
                    value={line.unit_cost}
                    onChange={(event) => setBillLine(index, { unit_cost: event.target.value })}
                  />
                </Field>
                <Field label="Tax %" error={errors[`lines.${index}.tax_percentage`]}>
                  <Input
                    value={line.tax_percentage ?? "0"}
                    onChange={(event) => setBillLine(index, { tax_percentage: event.target.value })}
                  />
                </Field>
                <Button
                  variant="secondary"
                  disabled={adhoc.lines.length <= 1}
                  onClick={() =>
                    setAdhoc((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }))
                  }
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
        )}
      </Modal>

      <Modal
        open={linesBill !== null}
        title={linesBill ? `Lines — ${linesBill.doc_number}` : "Lines"}
        onClose={() => setLinesBill(null)}
        wide
      >
        <DataTable
          columns={billLineColumns}
          rows={billLines.data}
          rowKey={(l) => l.id}
          loading={billLines.isLoading}
          error={billLines.error}
          onRetry={() => billLines.refetch()}
          empty={<EmptyState title="No lines" />}
        />
      </Modal>
    </>
  );
}
