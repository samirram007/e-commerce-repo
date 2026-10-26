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
import { formatDate, formatQty, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { ordersQueryOptions } from "../orders/queries";
import {
  createShipmentFormSchema,
  dispatchFormSchema,
  type DispatchFormInput,
  SHIPMENT_TRANSITIONS,
  type Shipment,
  type ShipmentLine,
} from "./schemas";
import {
  shipmentQueryOptions,
  shipmentsQueryOptions,
  useCreateShipment,
  useDispatchShipment,
  useTransitionShipment,
} from "./queries";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  ...Object.keys(SHIPMENT_TRANSITIONS).map((status) => ({ value: status, label: titleCase(status) })),
];

export function ShipmentsPage() {
  const { has } = usePermissions();
  const canFulfill = has("sales.fulfill");

  const [status, setStatus] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [orderError, setOrderError] = useState<Record<string, string>>({});

  const [selected, setSelected] = useState<Shipment | null>(null);
  const [transitionTo, setTransitionTo] = useState("");
  const [dispatchForm, setDispatchForm] = useState<DispatchFormInput>({ carrier: "mock" });
  const [dispatchErrors, setDispatchErrors] = useState<Record<string, string>>({});

  const shipments = useQuery(shipmentsQueryOptions({ status: status ?? undefined }));
  const orders = useQuery(ordersQueryOptions());
  const detail = useQuery(shipmentQueryOptions(selected?.id ?? "", selected !== null));

  const createShipment = useCreateShipment();
  const transitionShipment = useTransitionShipment();
  const dispatchShipment = useDispatchShipment();

  const orderOptions = useMemo(
    () =>
      (orders.data ?? [])
        .filter((order) => order.status === "paid" || order.status === "confirmed")
        .map((order) => ({
          value: order.id,
          label: `${order.doc_number} — ${titleCase(order.status)}`,
          hint: order.customer_id,
        })),
    [orders.data],
  );

  const currentStatus = detail.data?.status ?? selected?.status ?? "";
  const nextStatuses = SHIPMENT_TRANSITIONS[currentStatus] ?? [];
  const effectiveTransition = nextStatuses.includes(transitionTo)
    ? transitionTo
    : nextStatuses[0] ?? "";
  const transitionOptions = nextStatuses.map((value) => ({ value, label: titleCase(value) }));

  function openCreate() {
    setOrderId("");
    setOrderError({});
    setCreateOpen(true);
  }

  function submitCreate() {
    const parsed = createShipmentFormSchema.safeParse({ order_id: orderId });
    if (!parsed.success) {
      setOrderError(fieldErrors(parsed.error));
      return;
    }
    setOrderError({});
    createShipment.mutate(parsed.data.order_id, {
      onSuccess: () => setCreateOpen(false),
    });
  }

  function openManage(shipment: Shipment) {
    setSelected(shipment);
    setTransitionTo(SHIPMENT_TRANSITIONS[shipment.status]?.[0] ?? "");
    setDispatchForm({ carrier: "mock" });
    setDispatchErrors({});
  }

  function submitDispatch() {
    if (!selected) return;
    const parsed = dispatchFormSchema.safeParse(dispatchForm);
    if (!parsed.success) {
      setDispatchErrors(fieldErrors(parsed.error));
      return;
    }
    setDispatchErrors({});
    dispatchShipment.mutate({ id: selected.id, carrier: parsed.data.carrier });
  }

  const columns: Column<Shipment>[] = [
    { key: "doc", header: "Shipment", render: (s) => <strong>{s.doc_number}</strong> },
    { key: "order", header: "Order", render: (s) => s.order_id },
    { key: "status", header: "Status", render: (s) => <StatusBadge status={s.status} /> },
    { key: "carrier", header: "Carrier", render: (s) => s.carrier ?? "—" },
    { key: "tracking", header: "Tracking", render: (s) => s.tracking_number ?? "—" },
    { key: "dispatched", header: "Dispatched", render: (s) => formatDate(s.dispatched_at) },
    {
      key: "actions",
      header: "",
      render: (s) => (
        <Button variant="secondary" onClick={() => openManage(s)}>
          Manage
        </Button>
      ),
    },
  ];

  const lineColumns: Column<ShipmentLine>[] = [
    { key: "product", header: "Product", render: (l) => l.product_id },
    { key: "location", header: "From location", render: (l) => l.from_location_id },
    { key: "qty", header: "Qty", align: "right", render: (l) => formatQty(l.qty) },
  ];

  return (
    <>
      <PageHeader
        title="Shipments"
        description="Fulfill paid orders through picking, packing and dispatch"
        actions={canFulfill ? <Button onClick={openCreate}>New shipment</Button> : null}
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
          rows={shipments.data}
          rowKey={(s) => s.id}
          loading={shipments.isLoading}
          error={shipments.error}
          onRetry={() => shipments.refetch()}
          empty={<EmptyState title="No shipments" message="Create a shipment from a paid order." />}
        />
      </Card>

      <Sheet
        open={createOpen}
        title="New shipment"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreate} disabled={createShipment.isPending}>
              {createShipment.isPending ? "Creating…" : "Create"}
            </Button>
          </>
        }
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={createShipment.error} />
          <Field label="Order" error={orderError.order_id}>
            <SheetSelect
              value={orderId}
              options={orderOptions}
              onChange={setOrderId}
              loading={orders.isLoading}
              placeholder="Select a paid order"
            />
          </Field>
          {orderOptions.length === 0 ? (
            <div className="muted">No paid or confirmed orders are available to fulfil.</div>
          ) : null}
        </div>
      </Sheet>

      <Sheet
        open={selected !== null}
        title={selected ? selected.doc_number : "Shipment"}
        onClose={() => setSelected(null)}
      >
        <div className="modal-body" style={{ flex: 1 }}>
          <ErrorBanner error={detail.error} />
          <ErrorBanner error={transitionShipment.error} />
          <ErrorBanner error={dispatchShipment.error} />
          {selected ? (
            <div className="stack">
              <div className="grid-2">
                <div>
                  <div className="muted">Status</div>
                  <StatusBadge status={currentStatus} />
                </div>
                <div>
                  <div className="muted">Carrier</div>
                  <div>{selected.carrier ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Tracking</div>
                  <div>{selected.tracking_number ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Dispatched</div>
                  <div>{formatDate(selected.dispatched_at)}</div>
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

              {canFulfill && nextStatuses.length > 0 ? (
                <Card title="Advance status">
                  <Field label="Next status">
                    <SheetSelect
                      value={effectiveTransition}
                      options={transitionOptions}
                      onChange={setTransitionTo}
                    />
                  </Field>
                  <Button
                    onClick={() =>
                      selected &&
                      effectiveTransition &&
                      transitionShipment.mutate({ id: selected.id, toStatus: effectiveTransition })
                    }
                    disabled={transitionShipment.isPending || !effectiveTransition}
                  >
                    {transitionShipment.isPending ? "Saving…" : "Advance"}
                  </Button>
                </Card>
              ) : null}

              {canFulfill && currentStatus === "packed" ? (
                <Card title="Dispatch">
                  <Field label="Carrier" error={dispatchErrors.carrier}>
                    <Input
                      value={dispatchForm.carrier}
                      onChange={(event) =>
                        setDispatchForm((prev) => ({ ...prev, carrier: event.target.value }))
                      }
                    />
                  </Field>
                  <Button onClick={submitDispatch} disabled={dispatchShipment.isPending}>
                    {dispatchShipment.isPending ? "Dispatching…" : "Dispatch"}
                  </Button>
                </Card>
              ) : null}
            </div>
          ) : null}
        </div>
      </Sheet>
    </>
  );
}
