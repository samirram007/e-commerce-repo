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
  PageHeader,
  StatusBadge,
  Textarea,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDateTime, formatMoney, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { invoicesQueryOptions } from "../invoicing/queries";
import {
  PAYMENT_DIRECTIONS,
  PAYMENT_METHODS,
  paymentFormSchema,
  type Allocation,
  type Payment,
  type PaymentCreateInput,
  type PaymentFormInput,
} from "./schemas";
import {
  paymentAllocationsQueryOptions,
  paymentCustomersQueryOptions,
  paymentVendorsQueryOptions,
  paymentsQueryOptions,
  useCreatePayment,
} from "./queries";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): PaymentFormInput {
  return {
    direction: "receipt",
    method: "bank",
    party_id: "",
    amount: "0",
    occurred_at: today(),
    notes: "",
    allocate_invoice_id: null,
    allocation_amount: "0",
  };
}

export function PaymentsPage() {
  const { has } = usePermissions();
  const canManage = has("payments.manage");

  const [directionFilter, setDirectionFilter] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<PaymentFormInput>(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<Payment | null>(null);

  const payments = useQuery(paymentsQueryOptions());
  const customers = useQuery(paymentCustomersQueryOptions());
  const vendors = useQuery(paymentVendorsQueryOptions());
  const invoices = useQuery(invoicesQueryOptions());
  const allocations = useQuery(paymentAllocationsQueryOptions(detail?.id ?? ""));
  const createPayment = useCreatePayment();

  const customerOptions = useMemo(
    () => (customers.data ?? []).map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })),
    [customers.data],
  );
  const vendorOptions = useMemo(
    () => (vendors.data ?? []).map((v) => ({ value: v.id, label: `${v.code} — ${v.name}` })),
    [vendors.data],
  );
  const invoiceOptions = useMemo(
    () =>
      (invoices.data ?? [])
        .filter((i) => i.status === "posted")
        .map((i) => ({
          value: i.id,
          label: `${i.doc_number} — ${i.customer_name}`,
          hint: formatMoney(i.total, i.currency),
        })),
    [invoices.data],
  );

  const partyOptions = form.direction === "receipt" ? customerOptions : vendorOptions;
  const partyLoading = form.direction === "receipt" ? customers.isLoading : vendors.isLoading;

  const rows = useMemo(
    () =>
      (payments.data ?? []).filter((p) => !directionFilter || p.direction === directionFilter),
    [payments.data, directionFilter],
  );

  function setField<K extends keyof PaymentFormInput>(key: K, value: PaymentFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function submit() {
    const parsed = paymentFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    const value = parsed.data;
    const input: PaymentCreateInput = {
      direction: value.direction,
      method: value.method,
      party_type: value.direction === "receipt" ? "customer" : "vendor",
      party_id: value.party_id,
      amount: value.amount,
      occurred_at: value.occurred_at,
      notes: value.notes,
      allocations:
        value.allocate_invoice_id && Number(value.allocation_amount) > 0
          ? [
              {
                document_type: "invoice",
                document_id: value.allocate_invoice_id,
                amount: value.allocation_amount,
              },
            ]
          : undefined,
    };
    createPayment.mutate(input, {
      onSuccess: () => {
        setCreateOpen(false);
        setForm(emptyForm());
      },
    });
  }

  const columns: Column<Payment>[] = [
    { key: "ref", header: "Reference", render: (p) => <strong>{p.provider_ref ?? "—"}</strong> },
    { key: "direction", header: "Direction", render: (p) => <StatusBadge status={p.direction} /> },
    { key: "method", header: "Method", render: (p) => titleCase(p.method) },
    { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
    { key: "amount", header: "Amount", align: "right", render: (p) => formatMoney(p.amount, p.currency) },
    { key: "occurred", header: "Occurred", render: (p) => formatDateTime(p.occurred_at) },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setDetail(p)}>
            Allocations
          </Button>
        </span>
      ),
    },
  ];

  const allocationColumns: Column<Allocation>[] = [
    { key: "type", header: "Document", render: (a) => titleCase(a.document_type ?? "—") },
    { key: "id", header: "Document id", render: (a) => a.document_id },
    { key: "amount", header: "Amount", align: "right", render: (a) => formatMoney(a.amount) },
  ];

  return (
    <>
      <PageHeader
        title="Payments"
        description="Manual receipts and payment vouchers"
        actions={canManage ? <Button onClick={() => setCreateOpen(true)}>New payment</Button> : null}
      />

      <Card>
        <div className="form-row">
          <Field label="Direction">
            <SheetSelect
              value={directionFilter}
              options={PAYMENT_DIRECTIONS.map((d) => ({ value: d, label: titleCase(d) }))}
              onChange={setDirectionFilter}
              placeholder="All directions"
            />
          </Field>
        </div>
      </Card>

      <ErrorBanner error={createPayment.error} />

      <Card>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(p) => p.id}
          loading={payments.isLoading}
          error={payments.error}
          onRetry={() => payments.refetch()}
          empty={<EmptyState title="No payments" message="Record your first receipt or voucher." />}
        />
      </Card>

      <Modal
        open={createOpen}
        title="New payment"
        onClose={() => setCreateOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createPayment.isPending}>
              {createPayment.isPending ? "Saving…" : "Record"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createPayment.error} />
        <div className="grid-2">
          <Field label="Direction" error={errors.direction}>
            <SheetSelect
              value={form.direction}
              options={PAYMENT_DIRECTIONS.map((d) => ({ value: d, label: titleCase(d) }))}
              onChange={(value) => {
                setField("direction", value as PaymentFormInput["direction"]);
                setField("party_id", "");
                setField("allocate_invoice_id", null);
              }}
            />
          </Field>
          <Field label="Method" error={errors.method}>
            <SheetSelect
              value={form.method}
              options={PAYMENT_METHODS.map((m) => ({ value: m, label: titleCase(m) }))}
              onChange={(value) => setField("method", value as PaymentFormInput["method"])}
            />
          </Field>
        </div>
        <div className="grid-2">
          <Field
            label={form.direction === "receipt" ? "Customer" : "Vendor"}
            error={errors.party_id}
          >
            <SheetSelect
              value={form.party_id || null}
              options={partyOptions}
              onChange={(value) => setField("party_id", value)}
              loading={partyLoading}
            />
          </Field>
          <Field label="Amount" error={errors.amount}>
            <Input value={form.amount} onChange={(event) => setField("amount", event.target.value)} />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Occurred at" error={errors.occurred_at}>
            <Input
              type="date"
              value={form.occurred_at}
              onChange={(event) => setField("occurred_at", event.target.value)}
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

        {form.direction === "receipt" ? (
          <div className="grid-2">
            <Field label="Allocate to invoice" error={errors.allocate_invoice_id}>
              <SheetSelect
                value={form.allocate_invoice_id}
                options={invoiceOptions}
                onChange={(value) => setField("allocate_invoice_id", value)}
                placeholder="Leave unallocated"
                loading={invoices.isLoading}
              />
            </Field>
            <Field label="Allocation amount" error={errors.allocation_amount}>
              <Input
                value={form.allocation_amount}
                onChange={(event) => setField("allocation_amount", event.target.value)}
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      <Sheet
        open={detail !== null}
        title={detail ? `Payment ${detail.provider_ref ?? detail.id}` : "Payment"}
        onClose={() => setDetail(null)}
      >
        {detail ? (
          <div style={{ padding: 18 }}>
            <div className="grid-2">
              <div>
                <div className="muted">Direction</div>
                <div>
                  <StatusBadge status={detail.direction} />
                </div>
              </div>
              <div>
                <div className="muted">Status</div>
                <div>
                  <StatusBadge status={detail.status} />
                </div>
              </div>
              <div>
                <div className="muted">Method</div>
                <div>{titleCase(detail.method)}</div>
              </div>
              <div>
                <div className="muted">Amount</div>
                <div>{formatMoney(detail.amount, detail.currency)}</div>
              </div>
            </div>
            <h3 className="card-title" style={{ marginTop: 18 }}>
              Allocations
            </h3>
            <DataTable
              columns={allocationColumns}
              rows={allocations.data}
              rowKey={(a) => a.id}
              loading={allocations.isLoading}
              error={allocations.error}
              onRetry={() => allocations.refetch()}
              empty={<EmptyState title="Nothing allocated" message="This payment is unallocated." />}
            />
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
