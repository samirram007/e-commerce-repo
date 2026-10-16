import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  Field,
  Input,
  PageHeader,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { formatDateTime, titleCase } from "../../lib/format";
import { auditQueryOptions } from "./queries";
import type { AuditRow } from "./schemas";

const LIMITS = ["50", "100", "200", "500"];

function pretty(value: string | null): string {
  if (!value) return "—";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

export function AuditPage() {
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [limit, setLimit] = useState("100");
  const [detail, setDetail] = useState<AuditRow | null>(null);

  const audit = useQuery(auditQueryOptions({ limit: Number(limit) }));

  const rows = useMemo(() => {
    const actionQuery = action.trim().toLowerCase();
    const entityQuery = entityType.trim().toLowerCase();
    return (audit.data ?? []).filter(
      (row) =>
        (!actionQuery || row.action.toLowerCase().includes(actionQuery)) &&
        (!entityQuery || row.entity_type.toLowerCase().includes(entityQuery)),
    );
  }, [audit.data, action, entityType]);

  const columns: Column<AuditRow>[] = [
    { key: "created", header: "When", render: (r) => formatDateTime(r.created_at) },
    { key: "action", header: "Action", render: (r) => <strong>{r.action}</strong> },
    { key: "entity", header: "Entity", render: (r) => titleCase(r.entity_type) },
    { key: "entity_id", header: "Entity id", render: (r) => r.entity_id ?? "—" },
    { key: "actor", header: "Actor", render: (r) => r.actor_user_id ?? "—" },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setDetail(r)}>
            View
          </Button>
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Audit log" description="Append-only record of company activity" />

      <Card>
        <div className="form-row">
          <Field label="Action">
            <Input
              value={action}
              placeholder="e.g. invoice.posted"
              onChange={(event) => setAction(event.target.value)}
            />
          </Field>
          <Field label="Entity">
            <Input
              value={entityType}
              placeholder="e.g. customer_invoice"
              onChange={(event) => setEntityType(event.target.value)}
            />
          </Field>
          <Field label="Limit">
            <SheetSelect
              value={limit}
              options={LIMITS.map((value) => ({ value, label: value }))}
              onChange={setLimit}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          loading={audit.isLoading}
          error={audit.error}
          onRetry={() => audit.refetch()}
          empty={<EmptyState title="No audit entries" message="Activity will appear here." />}
        />
      </Card>

      <Sheet
        open={detail !== null}
        title={detail ? detail.action : "Audit entry"}
        onClose={() => setDetail(null)}
      >
        {detail ? (
          <div style={{ padding: 18 }}>
            <div className="grid-2">
              <div>
                <div className="muted">When</div>
                <div>{formatDateTime(detail.created_at)}</div>
              </div>
              <div>
                <div className="muted">Entity</div>
                <div>{titleCase(detail.entity_type)}</div>
              </div>
              <div>
                <div className="muted">Entity id</div>
                <div>{detail.entity_id ?? "—"}</div>
              </div>
              <div>
                <div className="muted">Actor</div>
                <div>{detail.actor_user_id ?? "—"}</div>
              </div>
            </div>
            <h3 className="card-title" style={{ marginTop: 18 }}>
              Before
            </h3>
            <pre>{pretty(detail.before_data)}</pre>
            <h3 className="card-title" style={{ marginTop: 18 }}>
              After
            </h3>
            <pre>{pretty(detail.after_data)}</pre>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
