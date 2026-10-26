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
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatDate } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { accountsQueryOptions } from "../accounting/queries";
import {
  fiscalYearPeriodsQueryOptions,
  fiscalYearsQueryOptions,
  useCloseFiscalYear,
  useClosePeriod,
  useCreateFiscalYear,
  useForwardFiscalYear,
  usePostOpeningBalances,
} from "./queries";
import {
  fiscalYearFormSchema,
  openingBalancesPayloadSchema,
  type FiscalYear,
  type FiscalYearFormInput,
  type FiscalYearPeriod,
} from "./schemas";

const EMPTY_FISCAL: FiscalYearFormInput = { name: "", start_date: "", end_date: "" };

interface OpeningLine {
  account_code: string;
  side: "debit" | "credit";
  amount: string;
}

const EMPTY_LINE: OpeningLine = { account_code: "", side: "debit", amount: "" };

/**
 * Fiscal years with the full year-end lifecycle: monthly accounting periods,
 * opening balances (fresh/new database), close (P&L → retained earnings) and
 * forward (carry closing balances into the next year). Each row opens a
 * management sheet so the whole lifecycle stays in one place.
 */
export function FiscalYearsTab() {
  const { has } = usePermissions();
  const canManage = has("fiscal.manage");
  // Opening/close/forward post journals server-side under both permissions.
  const canPost = has("accounting.journal.post");
  const canRunLifecycle = canManage && canPost;

  const fiscalYears = useQuery(fiscalYearsQueryOptions());
  const createFiscalYear = useCreateFiscalYear();

  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FiscalYearFormInput>(EMPTY_FISCAL);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Lifecycle UI state — the managed year is re-derived from the query so
  // mutations (close/forward) reflect immediately in the sheet.
  const [managingId, setManagingId] = useState<string | null>(null);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [forwardingId, setForwardingId] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Opening-balances line editor.
  const [openingLines, setOpeningLines] = useState<OpeningLine[]>([
    { ...EMPTY_LINE },
    { ...EMPTY_LINE },
  ]);
  const [openingDesc, setOpeningDesc] = useState("");
  const [openingError, setOpeningError] = useState<string | null>(null);

  const managing = useMemo(
    () => fiscalYears.data?.find((fy) => fy.id === managingId) ?? null,
    [fiscalYears.data, managingId],
  );
  const closing = useMemo(
    () => fiscalYears.data?.find((fy) => fy.id === closingId) ?? null,
    [fiscalYears.data, closingId],
  );
  const forwarding = useMemo(
    () => fiscalYears.data?.find((fy) => fy.id === forwardingId) ?? null,
    [fiscalYears.data, forwardingId],
  );
  const opening = useMemo(
    () => fiscalYears.data?.find((fy) => fy.id === openingId) ?? null,
    [fiscalYears.data, openingId],
  );

  const periods = useQuery(fiscalYearPeriodsQueryOptions(managingId ?? ""));
  const accounts = useQuery(accountsQueryOptions());
  const closePeriod = useClosePeriod(managingId ?? "");
  const closeYear = useCloseFiscalYear();
  const forwardYear = useForwardFiscalYear();
  const postOpening = usePostOpeningBalances();

  const accountOptions = useMemo(
    () => (accounts.data ?? []).map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [accounts.data],
  );

  const openingTotals = useMemo(() => {
    let debit = 0;
    let credit = 0;
    for (const line of openingLines) {
      const amount = Number(line.amount) || 0;
      if (line.side === "debit") debit += amount;
      else credit += amount;
    }
    return { debit, credit, balanced: debit > 0 && Math.abs(debit - credit) < 0.005 };
  }, [openingLines]);

  const rows = useMemo(() => {
    const all = fiscalYears.data ?? [];
    if (statusFilter === "open") return all.filter((fy) => fy.is_open);
    if (statusFilter === "closed") return all.filter((fy) => !fy.is_open);
    return all;
  }, [fiscalYears.data, statusFilter]);

  function submitCreate() {
    const parsed = fiscalYearFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createFiscalYear.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_FISCAL);
      },
    });
  }

  function setOpeningLine(index: number, patch: Partial<OpeningLine>) {
    setOpeningLines((prev) =>
      prev.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    );
  }

  function submitOpening() {
    if (!opening) return;
    const parsed = openingBalancesPayloadSchema.safeParse({
      description: openingDesc.trim() ? openingDesc.trim() : undefined,
      lines: openingLines.map((line) => ({
        account_code: line.account_code,
        side: line.side,
        amount: line.amount,
      })),
    });
    if (!parsed.success) {
      setOpeningError(fieldErrors(parsed.error).lines ?? "Check the opening balance lines");
      return;
    }
    if (!openingTotals.balanced) {
      setOpeningError("Debits and credits must be equal and greater than zero");
      return;
    }
    setOpeningError(null);
    postOpening.mutate(
      { fiscalYearId: opening.id, input: parsed.data },
      {
        onSuccess: (result) => {
          setOpeningId(null);
          setOpeningLines([{ ...EMPTY_LINE }, { ...EMPTY_LINE }]);
          setOpeningDesc("");
          setNotice(`Opening balances posted as ${result.doc_number}.`);
        },
      },
    );
  }

  const fyLabel = (fy: FiscalYear) =>
    fy.name?.trim() ? fy.name : `${formatDate(fy.start_date)} → ${formatDate(fy.end_date)}`;

  const columns: Column<FiscalYear>[] = [
    { key: "name", header: "Name", render: (fy) => <strong>{fy.name || "—"}</strong> },
    { key: "start", header: "Start", render: (fy) => formatDate(fy.start_date) },
    { key: "end", header: "End", render: (fy) => formatDate(fy.end_date) },
    {
      key: "status",
      header: "Status",
      render: (fy) => (
        <Badge tone={fy.is_open ? "ok" : "bad"}>{fy.is_open ? "open" : "closed"}</Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (fy) =>
        canManage ? (
          <Button
            variant="secondary"
            onClick={() => {
              setNotice(null);
              setManagingId(fy.id);
            }}
          >
            Manage
          </Button>
        ) : null,
    },
  ];

  const periodColumns: Column<FiscalYearPeriod>[] = [
    {
      key: "range",
      header: "Period",
      render: (p) => `${formatDate(p.start_date)} → ${formatDate(p.end_date)}`,
    },
    {
      key: "status",
      header: "Status",
      render: (p) => (
        <Badge tone={p.is_open ? "ok" : "bad"}>{p.is_open ? "open" : "closed"}</Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (p) =>
        canManage && managing?.is_open && p.is_open ? (
          <Button
            variant="secondary"
            disabled={closePeriod.isPending}
            onClick={() => closePeriod.mutate(p.id)}
          >
            Close
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <Card
        title="Fiscal years"
        actions={canManage ? <Button onClick={() => setOpen(true)}>New fiscal year</Button> : null}
      >
        <div className="form-row" style={{ marginBottom: 12 }}>
          <Field label="Status">
            <SheetSelect
              value={statusFilter ?? ""}
              options={[
                { value: "", label: "All" },
                { value: "open", label: "Open" },
                { value: "closed", label: "Closed" },
              ]}
              onChange={(value) => setStatusFilter(value === "" ? null : value)}
              placeholder="All"
            />
          </Field>
        </div>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(fy) => fy.id}
          loading={fiscalYears.isLoading}
          error={fiscalYears.error}
          onRetry={() => fiscalYears.refetch()}
          empty={<EmptyState title="No fiscal years" message="Define your accounting calendar." />}
        />
      </Card>

      {/* ---------------------------------------------------- create modal */}
      <Modal
        open={open}
        title="New fiscal year"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCreate} disabled={createFiscalYear.isPending}>
              {createFiscalYear.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createFiscalYear.error} />
        <Field label="Name" error={errors.name} hint="Optional — defaults to the date range.">
          <Input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
          />
        </Field>
        <div className="grid-2">
          <Field label="Start date" error={errors.start_date}>
            <Input
              type="date"
              value={form.start_date}
              onChange={(event) => setForm((prev) => ({ ...prev, start_date: event.target.value }))}
            />
          </Field>
          <Field label="End date" error={errors.end_date}>
            <Input
              type="date"
              value={form.end_date}
              onChange={(event) => setForm((prev) => ({ ...prev, end_date: event.target.value }))}
            />
          </Field>
        </div>
      </Modal>

      {/* ---------------------------------------------- management sheet */}
      <Sheet
        open={managing !== null}
        title={managing ? `Manage ${fyLabel(managing)}` : "Fiscal year"}
        onClose={() => setManagingId(null)}
      >
        {managing ? (
          <div style={{ padding: 18 }}>
            <ErrorBanner error={closePeriod.error} />
            {notice ? (
              <div className="pill" style={{ marginBottom: 12 }}>
                {notice}
              </div>
            ) : null}

            <div className="grid-2">
              <div>
                <div className="muted">Range</div>
                <div>
                  {formatDate(managing.start_date)} → {formatDate(managing.end_date)}
                </div>
              </div>
              <div>
                <div className="muted">Status</div>
                <div>
                  <Badge tone={managing.is_open ? "ok" : "bad"}>
                    {managing.is_open ? "open" : "closed"}
                  </Badge>
                </div>
              </div>
            </div>

            {canRunLifecycle ? (
              <div className="toolbar" style={{ marginTop: 14 }}>
                {managing.is_open ? (
                  <>
                    <Button variant="secondary" onClick={() => setOpeningId(managing.id)}>
                      Opening balances…
                    </Button>
                    <Button variant="danger" onClick={() => setClosingId(managing.id)}>
                      Close fiscal year…
                    </Button>
                  </>
                ) : (
                  <Button onClick={() => setForwardingId(managing.id)}>
                    Forward to next year…
                  </Button>
                )}
              </div>
            ) : null}

            <h3 className="card-title" style={{ marginTop: 18 }}>
              Accounting periods
            </h3>
            <DataTable
              columns={periodColumns}
              rows={periods.data}
              rowKey={(p) => p.id}
              loading={periods.isLoading}
              error={periods.error}
              onRetry={() => periods.refetch()}
              empty={<EmptyState title="No periods" message="This year has no monthly periods." />}
            />
          </div>
        ) : null}
      </Sheet>

      {/* --------------------------------------- opening balances modal */}
      <Modal
        open={opening !== null}
        title={opening ? `Opening balances — ${fyLabel(opening)}` : "Opening balances"}
        onClose={() => setOpeningId(null)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpeningId(null)}>
              Cancel
            </Button>
            <Button
              onClick={submitOpening}
              disabled={postOpening.isPending || !openingTotals.balanced}
            >
              {postOpening.isPending ? "Posting…" : "Post opening balances"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={postOpening.error} />
        <p className="muted">
          Posted on {opening ? formatDate(opening.start_date) : "—"} as the year's first entry.
          Only allowed while the year has no posted activity (fresh/new database).
        </p>
        {openingError ? <div className="error-text">{openingError}</div> : null}
        <Field label="Description">
          <Input
            value={openingDesc}
            placeholder="Opening balances"
            onChange={(event) => setOpeningDesc(event.target.value)}
          />
        </Field>

        <div className="card-head" style={{ marginTop: 8 }}>
          <div className="card-title">Lines</div>
          <Button
            variant="secondary"
            onClick={() => setOpeningLines((prev) => [...prev, { ...EMPTY_LINE }])}
          >
            Add line
          </Button>
        </div>
        {openingLines.map((line, index) => (
          <div key={index} className="grid-3" style={{ alignItems: "end", marginBottom: 8 }}>
            <Field label="Account">
              <SheetSelect
                value={line.account_code || null}
                options={accountOptions}
                onChange={(value) => setOpeningLine(index, { account_code: value ?? "" })}
                loading={accounts.isLoading}
                placeholder="Select account"
              />
            </Field>
            <Field label="Side">
              <SheetSelect
                value={line.side}
                options={[
                  { value: "debit", label: "Debit" },
                  { value: "credit", label: "Credit" },
                ]}
                onChange={(value) =>
                  setOpeningLine(index, { side: value === "credit" ? "credit" : "debit" })
                }
              />
            </Field>
            <Field label="Amount">
              <Input
                value={line.amount}
                inputMode="decimal"
                onChange={(event) => setOpeningLine(index, { amount: event.target.value })}
              />
            </Field>
            <div className="toolbar">
              <Button
                variant="danger"
                onClick={() => setOpeningLines((prev) => prev.filter((_, i) => i !== index))}
                disabled={openingLines.length <= 2}
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
        <div className={openingTotals.balanced ? "muted" : "error-text"}>
          Debits {openingTotals.debit.toFixed(2)} · Credits {openingTotals.credit.toFixed(2)}
          {openingTotals.balanced ? " · balanced" : " · not balanced"}
        </div>
      </Modal>

      {/* ------------------------------------------------- close modal */}
      <Modal
        open={closing !== null}
        title="Close fiscal year"
        onClose={() => setClosingId(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setClosingId(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={closeYear.isPending}
              onClick={() => {
                if (!closing) return;
                closeYear.mutate(closing.id, {
                  onSuccess: (result) => {
                    setClosingId(null);
                    setNotice(
                      result.closing_entry_id
                        ? `Year closed. Closing entry ${result.closing_entry_id.slice(0, 8)} posted.`
                        : "Year closed.",
                    );
                  },
                });
              }}
            >
              {closeYear.isPending ? "Closing…" : "Close year"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={closeYear.error} />
        {closing ? (
          <>
            <p>
              Closing <strong>{fyLabel(closing)}</strong> will:
            </p>
            <ul>
              <li>
                Post a year-end closing entry moving profit/loss into Retained Earnings.
              </li>
              <li>Seal every accounting period — no further postings into this year.</li>
            </ul>
            <p className="muted">This cannot be undone.</p>
          </>
        ) : null}
      </Modal>

      {/* ----------------------------------------------- forward modal */}
      <Modal
        open={forwarding !== null}
        title="Forward balances to next year"
        onClose={() => setForwardingId(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setForwardingId(null)}>
              Cancel
            </Button>
            <Button
              disabled={forwardYear.isPending}
              onClick={() => {
                if (!forwarding) return;
                forwardYear.mutate(forwarding.id, {
                  onSuccess: (result) => {
                    setForwardingId(null);
                    setNotice(
                      `Forwarded ${result.accounts_carried} balances as ${result.doc_number}` +
                        (result.to_created ? " (next year created)." : "."),
                    );
                  },
                });
              }}
            >
              {forwardYear.isPending ? "Forwarding…" : "Forward"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={forwardYear.error} />
        {forwarding ? (
          <>
            <p>
              Forwarding <strong>{fyLabel(forwarding)}</strong> will:
            </p>
            <ul>
              <li>Create the next fiscal year if it does not exist yet.</li>
              <li>
                Post one balanced carry-forward entry with the year's closing balances on the
                new year's first day.
              </li>
            </ul>
            <p className="muted">
              Requires this year to be closed and the next year to be open and free of posted
              entries.
            </p>
          </>
        ) : null}
      </Modal>
    </>
  );
}
