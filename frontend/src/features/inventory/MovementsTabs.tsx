import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, ErrorBanner, Field, Input, Modal, Textarea } from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { fieldErrors } from "../../lib/zod-utils";
import {
  locationOptionsQueryOptions,
  productOptionsQueryOptions,
  useAdjustment,
  useTransfer,
} from "./queries";
import {
  ADJUSTMENT_DIRECTIONS,
  adjustmentFormSchema,
  transferFormSchema,
  type AdjustmentFormInput,
  type TransferFormInput,
} from "./schemas";

function binOptionsOf(
  locations: { id: string; code: string; name: string; location_type: string }[] | undefined,
) {
  return (locations ?? [])
    .filter((l) => l.location_type === "bin")
    .map((l) => ({ value: l.id, label: `${l.code} — ${l.name}` }));
}

const EMPTY_TRANSFER: TransferFormInput = {
  product_id: "",
  from_location_id: "",
  to_location_id: "",
  quantity: "1",
};

export function TransfersTab() {
  const { has } = usePermissions();
  const canManage = has("inventory.manage");

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const transfer = useTransfer();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TransferFormInput>(EMPTY_TRANSFER);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string | null>(null);

  const productSelect = useMemo(
    () => (products.data ?? []).map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` })),
    [products.data],
  );
  const binOptions = useMemo(() => binOptionsOf(locations.data), [locations.data]);

  function submit() {
    const parsed = transferFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    transfer.mutate(
      {
        product_id: parsed.data.product_id,
        from_location_id: parsed.data.from_location_id,
        to_location_id: parsed.data.to_location_id,
        quantity: parsed.data.quantity,
      },
      {
        onSuccess: (data) => {
          setResult(data.transfer_id);
          setOpen(false);
          setForm(EMPTY_TRANSFER);
        },
      },
    );
  }

  return (
    <>
      <Card>
        <p className="muted">
          Move stock between bin-level locations in the same warehouse. Transfers write a paired
          ledger entry and post the offsetting GL entry.
        </p>
        <ErrorBanner error={transfer.error} />
        {result ? <p className="muted">Transfer posted: {result}</p> : null}
        {canManage ? <Button onClick={() => setOpen(true)}>New transfer</Button> : null}
      </Card>

      <Modal
        open={open}
        title="New stock transfer"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={transfer.isPending}>
              {transfer.isPending ? "Transferring…" : "Transfer"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={transfer.error} />
        <Field label="Product" error={errors.product_id}>
          <SheetSelect
            value={form.product_id || null}
            options={productSelect}
            onChange={(value) => setForm((prev) => ({ ...prev, product_id: value }))}
            loading={products.isLoading}
          />
        </Field>
        <div className="grid-2">
          <Field label="From (bin)" error={errors.from_location_id}>
            <SheetSelect
              value={form.from_location_id || null}
              options={binOptions}
              onChange={(value) => setForm((prev) => ({ ...prev, from_location_id: value }))}
              emptyText="No bin locations"
            />
          </Field>
          <Field label="To (bin)" error={errors.to_location_id}>
            <SheetSelect
              value={form.to_location_id || null}
              options={binOptions}
              onChange={(value) => setForm((prev) => ({ ...prev, to_location_id: value }))}
              emptyText="No bin locations"
            />
          </Field>
        </div>
        <Field label="Quantity" error={errors.quantity}>
          <Input
            value={form.quantity}
            onChange={(event) => setForm((prev) => ({ ...prev, quantity: event.target.value }))}
          />
        </Field>
      </Modal>
    </>
  );
}

const EMPTY_ADJUSTMENT: AdjustmentFormInput = {
  product_id: "",
  location_id: "",
  quantity: "1",
  direction: "increase",
  reason: "",
};

export function AdjustmentsTab() {
  const { has } = usePermissions();
  const canManage = has("inventory.manage");

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const adjustment = useAdjustment();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<AdjustmentFormInput>(EMPTY_ADJUSTMENT);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string | null>(null);

  const productSelect = useMemo(
    () => (products.data ?? []).map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` })),
    [products.data],
  );
  const binOptions = useMemo(() => binOptionsOf(locations.data), [locations.data]);

  function submit() {
    const parsed = adjustmentFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    adjustment.mutate(
      {
        product_id: parsed.data.product_id,
        location_id: parsed.data.location_id,
        quantity: parsed.data.quantity,
        direction: parsed.data.direction,
        reason: parsed.data.reason?.trim() ? parsed.data.reason : undefined,
      },
      {
        onSuccess: (data) => {
          setResult(data.value);
          setOpen(false);
          setForm(EMPTY_ADJUSTMENT);
        },
      },
    );
  }

  return (
    <>
      <Card>
        <p className="muted">
          Post an inventory variance (increase or decrease) at a bin, with a reason. The movement is
          valued at the product&apos;s weighted-average cost and booked to inventory variance.
        </p>
        <ErrorBanner error={adjustment.error} />
        {result ? <p className="muted">Adjustment posted (value {result}).</p> : null}
        {canManage ? <Button onClick={() => setOpen(true)}>New adjustment</Button> : null}
      </Card>

      <Modal
        open={open}
        title="New stock adjustment"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={adjustment.isPending}>
              {adjustment.isPending ? "Posting…" : "Post adjustment"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={adjustment.error} />
        <div className="grid-2">
          <Field label="Product" error={errors.product_id}>
            <SheetSelect
              value={form.product_id || null}
              options={productSelect}
              onChange={(value) => setForm((prev) => ({ ...prev, product_id: value }))}
              loading={products.isLoading}
            />
          </Field>
          <Field label="Location (bin)" error={errors.location_id}>
            <SheetSelect
              value={form.location_id || null}
              options={binOptions}
              onChange={(value) => setForm((prev) => ({ ...prev, location_id: value }))}
              emptyText="No bin locations"
            />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Quantity" error={errors.quantity}>
            <Input
              value={form.quantity}
              onChange={(event) => setForm((prev) => ({ ...prev, quantity: event.target.value }))}
            />
          </Field>
          <Field label="Direction" error={errors.direction}>
            <SheetSelect
              value={form.direction}
              options={ADJUSTMENT_DIRECTIONS.map((d) => ({ value: d, label: d }))}
              onChange={(value) =>
                setForm((prev) => ({ ...prev, direction: value as AdjustmentFormInput["direction"] }))
              }
            />
          </Field>
        </div>
        <Field label="Reason" error={errors.reason}>
          <Textarea
            rows={2}
            value={form.reason ?? ""}
            onChange={(event) => setForm((prev) => ({ ...prev, reason: event.target.value }))}
          />
        </Field>
      </Modal>
    </>
  );
}
