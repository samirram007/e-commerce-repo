import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  StatusBadge,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatMoney, formatQty, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { orderQueryOptions, ordersQueryOptions } from "../orders/queries";
import {
  DISPOSITIONS,
  type Disposition,
  RETURN_STATUSES,
  type ReturnLine,
  returnCreateFormSchema,
  returnLineDraftSchema,
  type ReturnLineDraft,
  type ReturnLineDraftInput,
  type SalesReturn,
} from "./schemas";
import {
  returnQueryOptions,
  returnsQueryOptions,
  useApproveReturn,
  useCompleteReturn,
  useCreateReturn,
  useRejectReturn,
} from "./queries";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  ...RETURN_STATUSES.map((status) => ({ value: status, label: titleCase(status) })),
];

const DISPOSITION_OPTIONS = DISPOSITIONS.map((value) => ({ value, label: titleCase(value) }));

const EMPTY_DRAFT: ReturnLineDraftInput = {
  order_line_id: "",
  qty: "1",
  disposition: "resalable",
};

export function ReturnsPage() {
  const { has } = usePermissions();
  const canManage = has("returns.manage");

  const [status, setStatus] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [notes, setNotes] = useState("");
  const [draft, setDraft] = useState<ReturnLineDraftInput>(EMPTY_DRAFT);
  const [lines, setLines] = useState<ReturnLineDraft[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({});

  const [selected, setSelected] = useState<SalesReturn | null>(null);

  const returns = useQuery(returnsQueryOptions(status ?? ""));
  const orders = useQuery(ordersQueryOptions());
  const orderDetail = useQuery(orderQueryOptions(orderId, orderId !== ""));
  const detail = useQuery(returnQueryOptions(selected?.id ?? "", selected !== null));

  const createReturn = useCreateReturn();
  const approveReturn = useApproveReturn();
  const rejectReturn = useRejectReturn();
  const completeReturn = useCompleteReturn();

  const orderOptions = useMemo(
    () =>
      (orders.data ?? [])
        .filter((order) => order.invoice_id !== null)
        .map((order) => ({
          value: order.id,
          label: `${order.doc_number} — ${titleCase(order.status)}`,
          hint: formatMoney(order.total, order.currency),
        })),
    [orders.data],
  );

  const orderLines = orderDetail.data?.lines ?? [];
  const lineOptions = useMemo(
    () =>
      orderLines.map((line) => ({
        value: line.id,
        label: `${line.sku} — qty ${formatQty(line.qty)}`,
        hint: formatMoney(line.unit_price),
      })),
    [orderLines],
  );
  const skuByLine = useMemo(() => {
    const map = new Map<string, string>();
    for (const line of orderLines) map.set(line.id, line.sku);
    return map;
  }, [orderLines]);

  function openCreate() {
    setOrderId("");
    setNotes("");
    setDraft(EMPTY_DRAFT);
    setLines([]);
    setErrors({});
    setDraftErrors({});
    setCreateOpen(true);
  }

  function addLine() {
    const parsed = returnLineDraftSchema.safeParse(draft);
    if (!parsed.success) {
      setDraftErrors(fieldErrors(parsed.error));
      return;
    }
    setDraftErrors({});
    setLines((prev) => [...prev, parsed.data]);
    setDraft(EMPTY_DRAFT);
  }

  function submitCreate() {
    const parsed = returnCreateFormSchema.safeParse({ order_id: orderId, notes });
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    if (lines.length === 0) {
      setErrors({ lines: "Add at least one line" });
      return;
    }
    setErrors({});
    createReturn.mutate(
      {
        order_id: parsed.data.order_id,
        notes: parsed.data.notes,
        lines: lines.map((line) => ({
          order_line_id: line.order_line_id,
          qty: Number(line.qty),
          disposition: line.disposition,
        })),
      },
      {
        onSuccess: () => {
          setCreateOpen(false);
          setLines([]);
        },
      },
    );
  }

  const columns: Column<SalesReturn>[] = [
    { key: "doc", header: "Return", render: (r) => <strong>{r.doc_number}</strong> },
    { key: "order", header: "Order", render: (r) => r.order_id },
    { key: "customer", header: "Customer", render: (r) => r.customer_id },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "invoice", header: "Invoice", render: (r) => r.invoice_id ?? "—" },
    { key: "credit", header: "Credit note", render: (r) => r.credit_note_id ?? "—" },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <Button variant="secondary" onClick={() => setSelected(r)}>
          View
        </Button>
      ),
    },
  ];

  const lineColumns: Column<ReturnLine>[] = [
    { key: "product", header: "Product", render: (l) => l.product_id },
    { key: "qty", header: "Qty", align: "right", render: (l) => formatQty(l.qty) },
    { key: "price", header: "Unit price", align: "right", render: (l) => formatMoney(l.unit_price) },
    { key: "disposition", header: "Disposition", render: (l) => titleCase(l.disposition) },
  ];

  return (
    <>
      <PageHeader
        title="Returns"
        description="Customer returns, dispositions, credit notes and refunds"
        actions={canManage ? <Button onClick={openCreate}>New return</Button> : null}
      />

      <Card>
        <div className="form-row">
          <Field label="Status">
            <SheetSelect
              value={status ?? ""}
              options={STATUS_OPTIONS}
              onChange={(value) => setStatus(value || null)}
              placeholder="All statuses"
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={returns.data}
          rowKey={(r) => r.id}
          loading={returns.isLoading}
          error={returns.error}
          onRetry={() => returns.refetch()}
          empty={<EmptyState title="No returns" message="Request a return against a paid order." />}
        />
      </Card>

      <Sheet
        open={createOpen}
        title="New return"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreate} disabled={createReturn.isPending}>
              {createReturn.isPending ? "Requesting…" : "Request return"}
            </Button>
          </>
        }
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={createReturn.error} />
          <Field label="Order" error={errors.order_id}>
            <SheetSelect
              value={orderId}
              options={orderOptions}
              onChange={(value) => {
                setOrderId(value);
                setLines([]);
                setDraft(EMPTY_DRAFT);
              }}
              loading={orders.isLoading}
              placeholder="Select an invoiced order"
            />
          </Field>
          {orderOptions.length === 0 ? (
            <div className="muted">No invoiced orders are available to return.</div>
          ) : null}

          {orderId ? (
            <Card title="Add line">
              <Field label="Product" error={draftErrors.order_line_id}>
                <SheetSelect
                  value={draft.order_line_id}
                  options={lineOptions}
                  onChange={(value) => setDraft((prev) => ({ ...prev, order_line_id: value }))}
                  loading={orderDetail.isLoading}
                  placeholder="Select an order line"
                />
              </Field>
              <div className="grid-2">
                <Field label="Qty" error={draftErrors.qty}>
                  <Input
                    value={draft.qty}
                    onChange={(event) => setDraft((prev) => ({ ...prev, qty: event.target.value }))}
                  />
                </Field>
                <Field label="Disposition" error={draftErrors.disposition}>
                  <SheetSelect
                    value={draft.disposition}
                    options={DISPOSITION_OPTIONS}
                    onChange={(value) =>
                      setDraft((prev) => ({ ...prev, disposition: value as Disposition }))
                    }
                  />
                </Field>
              </div>
              <Button onClick={addLine} variant="secondary">
                Add line
              </Button>
            </Card>
          ) : null}

          <Card title="Lines">
            {errors.lines ? <div className="error-text">{errors.lines}</div> : null}
            {lines.length > 0 ? (
              <div className="stack">
                {lines.map((line) => (
                  <div className="toolbar" key={line.order_line_id}>
                    <span style={{ flex: 1 }}>
                      {skuByLine.get(line.order_line_id) ?? line.order_line_id} × {line.qty} (
                      {titleCase(line.disposition)})
                    </span>
                    <Button
                      variant="danger"
                      onClick={() =>
                        setLines((prev) =>
                          prev.filter((entry) => entry.order_line_id !== line.order_line_id),
                        )
                      }
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No lines" message="Add at least one line to return." />
            )}
          </Card>

          <Field label="Notes" error={errors.notes}>
            <Input value={notes} onChange={(event) => setNotes(event.target.value)} />
          </Field>
        </div>
      </Sheet>

      <Sheet
        open={selected !== null}
        title={selected ? selected.doc_number : "Return"}
        onClose={() => setSelected(null)}
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={detail.error} />
          <ErrorBanner error={approveReturn.error} />
          <ErrorBanner error={rejectReturn.error} />
          <ErrorBanner error={completeReturn.error} />
          {selected ? (
            <div className="stack">
              <div className="grid-2">
                <div>
                  <div className="muted">Status</div>
                  <StatusBadge status={selected.status} />
                </div>
                <div>
                  <div className="muted">Customer</div>
                  <div>{selected.customer_id}</div>
                </div>
                <div>
                  <div className="muted">Invoice</div>
                  <div>{selected.invoice_id ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Credit note</div>
                  <div>{selected.credit_note_id ?? "—"}</div>
                </div>
              </div>

              <Card title="Lines">
                <DataTable
                  columns={lineColumns}
                  rows={detail.data?.lines}
                  rowKey={(l) => l.id}
                  loading={detail.isLoading}
                  empty={<EmptyState title="No lines" />}
                />
              </Card>

              {canManage && selected.status === "requested" ? (
                <div className="toolbar">
                  <Button
                    onClick={() => approveReturn.mutate(selected.id)}
                    disabled={approveReturn.isPending}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => rejectReturn.mutate(selected.id)}
                    disabled={rejectReturn.isPending}
                  >
                    Reject
                  </Button>
                </div>
              ) : null}

              {canManage && selected.status === "approved" ? (
                <Button onClick={() => completeReturn.mutate(selected.id)} disabled={completeReturn.isPending}>
                  {completeReturn.isPending ? "Completing…" : "Complete & refund"}
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </Sheet>
    </>
  );
}
