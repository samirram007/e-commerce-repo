import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Kpi,
  KpiRow,
  Modal,
  StatusBadge,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate, formatMoney } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  runsQueryOptions,
  useCancelRun,
  useCreateRun,
  usePostRun,
} from "./queries";
import {
  MONTH_NAMES,
  runCreateFormSchema,
  type PayrollRun,
  type PayrollRunDetail,
  type RunCreateFormInput,
} from "./schemas";

function defaultRunForm(): RunCreateFormInput {
  const now = new Date();
  return {
    period_year: String(now.getFullYear()),
    period_month: String(Math.max(1, now.getMonth() + 1)) as RunCreateFormInput["period_month"],
  };
}

function periodLabel(run: { period_year: number; period_month: number }): string {
  const month = MONTH_NAMES[run.period_month - 1] ?? String(run.period_month);
  return `${month} ${run.period_year}`;
}

/**
 * Payroll runs lifecycle: create a draft run for a month (snapshotting every
 * active employee into payslips), inspect the payslips, then post it (one
 * balanced GL entry) or cancel the draft.
 */
export function RunsTab() {
  const { has } = usePermissions();
  const canManage = has("payroll.manage");

  const runs = useQuery(runsQueryOptions());
  const createRun = useCreateRun();
  const postRun = usePostRun();
  const cancelRun = useCancelRun();

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<RunCreateFormInput>(defaultRunForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<PayrollRunDetail | null>(null);
  const [confirm, setConfirm] = useState<{ run: PayrollRun; action: "post" | "cancel" } | null>(
    null,
  );

  function submitCreate() {
    const parsed = runCreateFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createRun.mutate(parsed.data, {
      onSuccess: (run) => {
        setCreateOpen(false);
        setDetail(run);
      },
    });
  }

  function runConfirm() {
    if (!confirm) return;
    const { run, action } = confirm;
    const mutation = action === "post" ? postRun : cancelRun;
    mutation.mutate(run.id, {
      onSuccess: (updated) => {
        setConfirm(null);
        setDetail(updated);
      },
    });
  }

  const columns: Column<PayrollRun>[] = [
    { key: "doc", header: "Doc #", render: (r) => <strong>{r.doc_number}</strong> },
    { key: "period", header: "Period", render: (r) => periodLabel(r) },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "employees", header: "Employees", align: "right", render: (r) => r.employee_count },
    { key: "gross", header: "Gross", align: "right", render: (r) => formatMoney(r.total_gross) },
    {
      key: "deductions",
      header: "Deductions",
      align: "right",
      render: (r) => formatMoney(r.total_deductions),
    },
    { key: "net", header: "Net", align: "right", render: (r) => formatMoney(r.total_net) },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (r) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setDetail(r as PayrollRunDetail)}>
            View
          </Button>
          {canManage && r.status === "draft" ? (
            <>
              <Button onClick={() => setConfirm({ run: r, action: "post" })}>Post</Button>
              <Button
                variant="danger"
                onClick={() => setConfirm({ run: r, action: "cancel" })}
              >
                Cancel
              </Button>
            </>
          ) : null}
        </span>
      ),
    },
  ];

  const payslipColumns: Column<PayrollRunDetail["payslips"][number]>[] = [
    { key: "code", header: "Code", render: (p) => <strong>{p.employee_code}</strong> },
    { key: "name", header: "Employee", render: (p) => p.employee_name },
    { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
    { key: "gross", header: "Gross", align: "right", render: (p) => formatMoney(p.gross) },
    {
      key: "deductions",
      header: "Deductions",
      align: "right",
      render: (p) => `${formatMoney(p.deductions)} (${p.deduction_rate}%)`,
    },
    { key: "net", header: "Net pay", align: "right", render: (p) => formatMoney(p.net_pay) },
  ];

  return (
    <>
      <Card
        title="Payroll runs"
        actions={
          canManage ? (
            <Button
              onClick={() => {
                setForm(defaultRunForm());
                setErrors({});
                setCreateOpen(true);
              }}
            >
              New run
            </Button>
          ) : null
        }
      >
        <ErrorBanner error={runs.error} />
        <DataTable
          columns={columns}
          rows={runs.data}
          rowKey={(r) => r.id}
          loading={runs.isLoading}
          error={runs.error}
          onRetry={() => runs.refetch()}
          empty={
            <EmptyState
              title="No payroll runs"
              message="Run payroll for a month to generate payslips for every active employee."
            />
          }
        />
      </Card>

      {/* --------------------------------------------------- create modal */}
      <Modal
        open={createOpen}
        title="New payroll run"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreate} disabled={createRun.isPending}>
              {createRun.isPending ? "Creating…" : "Create run"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createRun.error} />
        <p className="muted">
          Creates a draft run with payslips for every active employee. Posting it later books
          one balanced journal entry.
        </p>
        <div className="grid-2">
          <Field label="Year" error={errors.period_year}>
            <Input
              value={form.period_year}
              inputMode="numeric"
              maxLength={4}
              placeholder="2026"
              onChange={(event) =>
                setForm((prev) => ({ ...prev, period_year: event.target.value }))
              }
            />
          </Field>
          <Field label="Month" error={errors.period_month}>
            <SheetSelect
              value={form.period_month}
              options={MONTH_NAMES.map((name, index) => ({
                value: String(index + 1),
                label: name,
              }))}
              onChange={(value) =>
                setForm(
                  (prev) =>
                    ({ ...prev, period_month: value }) as RunCreateFormInput,
                )
              }
              placeholder="Month"
            />
          </Field>
        </div>
      </Modal>

      {/* --------------------------------------------------- confirm modal */}
      <Modal
        open={confirm !== null}
        title={confirm?.action === "post" ? "Post payroll run" : "Cancel payroll run"}
        onClose={() => setConfirm(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              Back
            </Button>
            <Button
              variant={confirm?.action === "cancel" ? "danger" : "primary"}
              disabled={postRun.isPending || cancelRun.isPending}
              onClick={runConfirm}
            >
              {confirm?.action === "post"
                ? postRun.isPending
                  ? "Posting…"
                  : "Post run"
                : cancelRun.isPending
                  ? "Cancelling…"
                  : "Cancel run"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={postRun.error ?? cancelRun.error} />
        {confirm ? (
          confirm.action === "post" ? (
            <>
              <p>
                Posting <strong>{confirm.run.doc_number}</strong> ({periodLabel(confirm.run)})
                will:
              </p>
              <ul>
                <li>Mark all payslips as posted.</li>
                <li>
                  Book one journal entry: salaries expense debited, withholdings + payroll
                  payable credited ({formatMoney(confirm.run.total_gross)} gross).
                </li>
              </ul>
              <p className="muted">A posted run must be reversed through Accounting.</p>
            </>
          ) : (
            <>
              <p>
                Cancel <strong>{confirm.run.doc_number}</strong> ({periodLabel(confirm.run)})?
                Payslips are voided and the period becomes available for a new run. Drafts only.
              </p>
            </>
          )
        ) : null}
      </Modal>

      {/* -------------------------------------------------- detail sheet */}
      <Sheet
        open={detail !== null}
        title={detail ? `Payroll ${detail.doc_number} — ${periodLabel(detail)}` : "Payroll run"}
        onClose={() => setDetail(null)}
      >
        {detail ? (
          <div style={{ padding: 18 }}>
            <div className="toolbar" style={{ marginBottom: 12 }}>
              <StatusBadge status={detail.status} />
              {detail.journal_entry_id ? (
                <span className="muted">Journal: {detail.journal_entry_id.slice(0, 8)}</span>
              ) : null}
              {detail.posted_at ? (
                <span className="muted">Posted {formatDate(detail.posted_at)}</span>
              ) : null}
            </div>

            <KpiRow>
              <Kpi label="Employees" value={detail.employee_count} />
              <Kpi label="Gross" value={formatMoney(detail.total_gross)} />
              <Kpi label="Deductions" value={formatMoney(detail.total_deductions)} />
              <Kpi label="Net" value={formatMoney(detail.total_net)} />
            </KpiRow>

            {canManage && detail.status === "draft" ? (
              <div className="toolbar" style={{ margin: "12px 0" }}>
                <Button onClick={() => setConfirm({ run: detail, action: "post" })}>
                  Post run
                </Button>
                <Button
                  variant="danger"
                  onClick={() => setConfirm({ run: detail, action: "cancel" })}
                >
                  Cancel run
                </Button>
              </div>
            ) : null}

            <h3 className="card-title" style={{ marginTop: 12 }}>
              Payslips
            </h3>
            <DataTable
              columns={payslipColumns}
              rows={detail.payslips}
              rowKey={(p) => p.id}
              empty={<EmptyState title="No payslips" message="This run has no payslips." />}
            />
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
