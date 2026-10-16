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
  StatusBadge,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatQty } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  countQueryOptions,
  locationOptionsQueryOptions,
  productOptionsQueryOptions,
  useAddCountLine,
  useCreateCount,
  usePostCount,
} from "./queries";
import {
  countLineFormSchema,
  createCountFormSchema,
  type CountLine,
  type CountLineFormInput,
  type CreateCountFormInput,
} from "./schemas";

interface TrackedCount {
  id: string;
  doc_number: string;
  location_id: string;
}

export function CountsTab() {
  const { has } = usePermissions();
  const canManage = has("inventory.manage");

  const products = useQuery(productOptionsQueryOptions());
  const locations = useQuery(locationOptionsQueryOptions());
  const createCount = useCreateCount();
  const addLine = useAddCountLine();
  const postCount = usePostCount();

  const [tracked, setTracked] = useState<TrackedCount[]>([]);
  const [openId, setOpenId] = useState("");
  const [manualId, setManualId] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCountFormInput>({ location_id: "" });
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});

  const [lineForm, setLineForm] = useState<CountLineFormInput>({ product_id: "", counted_qty: "0" });
  const [lineErrors, setLineErrors] = useState<Record<string, string>>({});

  const active = useQuery(countQueryOptions(openId));

  const productName = useMemo(() => {
    const map = new Map<string, string>();
    for (const product of products.data ?? []) map.set(product.id, `${product.sku} — ${product.name}`);
    return map;
  }, [products.data]);

  const locationLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const location of locations.data ?? []) map.set(location.id, `${location.code} — ${location.name}`);
    return map;
  }, [locations.data]);

  const binOptions = useMemo(
    () =>
      (locations.data ?? [])
        .filter((l) => l.location_type === "bin")
        .map((l) => ({ value: l.id, label: `${l.code} — ${l.name}` })),
    [locations.data],
  );
  const productOptions = useMemo(
    () => (products.data ?? []).map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` })),
    [products.data],
  );

  function submitCreate() {
    const parsed = createCountFormSchema.safeParse(createForm);
    if (!parsed.success) {
      setCreateErrors(fieldErrors(parsed.error));
      return;
    }
    setCreateErrors({});
    createCount.mutate(parsed.data.location_id, {
      onSuccess: (result) => {
        setTracked((prev) => [
          { id: result.id, doc_number: result.doc_number, location_id: parsed.data.location_id },
          ...prev,
        ]);
        setCreateOpen(false);
        setCreateForm({ location_id: "" });
        setOpenId(result.id);
        setLineForm({ product_id: "", counted_qty: "0" });
      },
    });
  }

  function submitLine() {
    if (!openId) return;
    const parsed = countLineFormSchema.safeParse(lineForm);
    if (!parsed.success) {
      setLineErrors(fieldErrors(parsed.error));
      return;
    }
    setLineErrors({});
    addLine.mutate(
      { id: openId, productId: parsed.data.product_id, countedQty: parsed.data.counted_qty },
      { onSuccess: () => setLineForm({ product_id: "", counted_qty: "0" }) },
    );
  }

  function closeCount() {
    setOpenId("");
    setLineErrors({});
    postCount.reset();
    addLine.reset();
  }

  const isOpenCount = active.data?.status === "open";
  const lineColumns: Column<CountLine>[] = [
    { key: "product", header: "Product", render: (l) => productName.get(l.product_id) ?? l.product_id },
    { key: "counted", header: "Counted", align: "right", render: (l) => formatQty(l.counted_qty) },
    { key: "system", header: "System", align: "right", render: (l) => formatQty(l.system_qty) },
    { key: "variance", header: "Variance", align: "right", render: (l) => formatQty(l.variance) },
  ];

  return (
    <>
      <Card>
        <div className="form-row">
          <Field label="Open a count by id">
            <Input
              value={manualId}
              placeholder="Stock count id"
              onChange={(event) => setManualId(event.target.value)}
            />
          </Field>
          <div className="toolbar" style={{ alignItems: "flex-end" }}>
            <Button
              variant="secondary"
              disabled={!manualId.trim()}
              onClick={() => {
                setOpenId(manualId.trim());
                setLineForm({ product_id: "", counted_qty: "0" });
              }}
            >
              Open
            </Button>
            {canManage ? <Button onClick={() => setCreateOpen(true)}>New count</Button> : null}
          </div>
        </div>

        {tracked.length > 0 ? (
          <table className="data">
            <thead>
              <tr>
                <th>Count</th>
                <th>Location</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {tracked.map((count) => (
                <tr key={count.id}>
                  <td>
                    <strong>{count.doc_number}</strong>
                  </td>
                  <td>{locationLabel.get(count.location_id) ?? count.location_id}</td>
                  <td style={{ textAlign: "right" }}>
                    <Button variant="secondary" onClick={() => setOpenId(count.id)}>
                      Open
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState
            title="No counts this session"
            message="Create a count or open an existing one by id."
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="New stock count"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreate} disabled={createCount.isPending}>
              {createCount.isPending ? "Creating…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createCount.error} />
        <Field label="Location (bin)" error={createErrors.location_id}>
          <SheetSelect
            value={createForm.location_id || null}
            options={binOptions}
            onChange={(value) => setCreateForm({ location_id: value })}
            emptyText="No bin locations"
          />
        </Field>
      </Modal>

      <Sheet
        open={openId.length > 0}
        title={active.data ? `Count ${active.data.doc_number}` : "Stock count"}
        onClose={closeCount}
        footer={
          <>
            <Button variant="secondary" onClick={closeCount}>
              Close
            </Button>
            {canManage && isOpenCount ? (
              <Button
                onClick={() => postCount.mutate(openId)}
                disabled={postCount.isPending}
              >
                {postCount.isPending ? "Posting…" : "Post count"}
              </Button>
            ) : null}
          </>
        }
      >
        <ErrorBanner error={active.error ?? addLine.error ?? postCount.error} />
        <div className="toolbar">
          <span>
            <StatusBadge status={active.data?.status} />
          </span>
          <span className="muted">
            {active.data ? locationLabel.get(active.data.location_id) ?? active.data.location_id : ""}
          </span>
        </div>

        <DataTable
          columns={lineColumns}
          rows={active.data?.lines}
          rowKey={(l) => l.id}
          loading={active.isLoading}
          error={active.error}
          onRetry={() => active.refetch()}
          empty={<EmptyState title="No lines" message="Add counted quantities below." />}
        />

        {canManage && isOpenCount ? (
          <div className="form-row">
            <Field label="Product" error={lineErrors.product_id}>
              <SheetSelect
                value={lineForm.product_id || null}
                options={productOptions}
                onChange={(value) => setLineForm((prev) => ({ ...prev, product_id: value }))}
                loading={products.isLoading}
              />
            </Field>
            <Field label="Counted qty" error={lineErrors.counted_qty}>
              <Input
                value={lineForm.counted_qty}
                onChange={(event) =>
                  setLineForm((prev) => ({ ...prev, counted_qty: event.target.value }))
                }
              />
            </Field>
            <Button
              variant="secondary"
              onClick={submitLine}
              disabled={addLine.isPending}
              style={{ alignSelf: "flex-end" }}
            >
              {addLine.isPending ? "Adding…" : "Add line"}
            </Button>
          </div>
        ) : active.data ? (
          <Badge tone="default">Count is {active.data.status}</Badge>
        ) : null}
      </Sheet>
    </>
  );
}
