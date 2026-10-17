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
  Kpi,
  KpiRow,
  Modal,
  PageHeader,
  StatusBadge,
  Tabs,
  type Column,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { usePeriodContext } from "../periods/period-context";
import { formatDate, formatMoney, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  ACCOUNT_TYPES,
  EMPTY_JOURNAL_LINE,
  SIDES,
  accountFormSchema,
  journalFormSchema,
  type Account,
  type AccountFormInput,
  type GeneralLedgerRow,
  type JournalEntry,
  type JournalFormInput,
  type JournalLine,
  type JournalLineFormInput,
  type TrialBalanceRow,
} from "./schemas";
import {
  accountsQueryOptions,
  balanceSheetQueryOptions,
  generalLedgerQueryOptions,
  journalEntriesQueryOptions,
  profitAndLossQueryOptions,
  trialBalanceQueryOptions,
  useCreateAccount,
  useCreateJournalEntry,
  useReverseJournalEntry,
} from "./queries";

type Tab = "accounts" | "journals" | "trial-balance" | "pnl" | "balance-sheet" | "gl";

const TABS: { key: Tab; label: string }[] = [
  { key: "accounts", label: "Chart of accounts" },
  { key: "journals", label: "Journal entries" },
  { key: "trial-balance", label: "Trial balance" },
  { key: "pnl", label: "P&L" },
  { key: "balance-sheet", label: "Balance sheet" },
  { key: "gl", label: "General ledger" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function startOfYear(): string {
  return `${new Date().getFullYear()}-01-01`;
}

function emptyJournalForm(): JournalFormInput {
  return {
    entry_date: today(),
    description: "",
    lines: [{ ...EMPTY_JOURNAL_LINE }, { ...EMPTY_JOURNAL_LINE }],
  };
}

const EMPTY_ACCOUNT_FORM: AccountFormInput = {
  code: "",
  name: "",
  account_type: "asset",
  normal_side: "debit",
};

export function AccountingPage() {
  const { has } = usePermissions();
  // The topbar fiscal-year switcher drives which entries the ledger/statement
  // queries report on; the backend filters on the entry's posted FY snapshot.
  const { fiscalYear } = usePeriodContext();
  const fiscalYearId = fiscalYear?.id ?? null;
  const canManageAccounts = has("accounting.accounts.manage");
  const canPost = has("accounting.journal.post");

  const [tab, setTab] = useState<Tab>("accounts");

  const [accountOpen, setAccountOpen] = useState(false);
  const [accountForm, setAccountForm] = useState<AccountFormInput>(EMPTY_ACCOUNT_FORM);
  const [accountErrors, setAccountErrors] = useState<Record<string, string>>({});

  const [journalOpen, setJournalOpen] = useState(false);
  const [journalForm, setJournalForm] = useState<JournalFormInput>(emptyJournalForm);
  const [journalErrors, setJournalErrors] = useState<Record<string, string>>({});
  const [detail, setDetail] = useState<JournalEntry | null>(null);

  const [tbFrom, setTbFrom] = useState("");
  const [tbTo, setTbTo] = useState("");
  const [pnlFrom, setPnlFrom] = useState(startOfYear());
  const [pnlTo, setPnlTo] = useState(today());
  const [bsAsOf, setBsAsOf] = useState(today());
  const [glAccount, setGlAccount] = useState<string | null>(null);
  const [glFrom, setGlFrom] = useState("");
  const [glTo, setGlTo] = useState("");

  const accounts = useQuery(accountsQueryOptions());
  const journals = useQuery(journalEntriesQueryOptions({ fiscalYearId: fiscalYearId ?? undefined }));
  const trialBalance = useQuery(
    trialBalanceQueryOptions({
      fromDate: tbFrom || undefined,
      toDate: tbTo || undefined,
      fiscalYearId: fiscalYearId ?? undefined,
    }),
  );
  const pnl = useQuery(profitAndLossQueryOptions(pnlFrom, pnlTo));
  const balanceSheet = useQuery(balanceSheetQueryOptions(bsAsOf));
  const generalLedger = useQuery(
    generalLedgerQueryOptions({
      accountCode: glAccount ?? undefined,
      fromDate: glFrom || undefined,
      toDate: glTo || undefined,
      fiscalYearId: fiscalYearId ?? undefined,
    }),
  );

  const createAccount = useCreateAccount();
  const createJournal = useCreateJournalEntry();
  const reverseJournal = useReverseJournalEntry();

  const accountOptions = useMemo(
    () => (accounts.data ?? []).map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [accounts.data],
  );

  const journalTotals = useMemo(() => {
    let debit = 0;
    let credit = 0;
    for (const line of journalForm.lines) {
      const amount = Number(line.amount) || 0;
      if (line.side === "debit") debit += amount;
      else credit += amount;
    }
    return { debit, credit, balanced: Math.abs(debit - credit) < 0.005 };
  }, [journalForm.lines]);

  function setJournalLine(index: number, patch: Partial<JournalLineFormInput>) {
    setJournalForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function addJournalLine() {
    setJournalForm((prev) => ({ ...prev, lines: [...prev.lines, { ...EMPTY_JOURNAL_LINE }] }));
  }

  function removeJournalLine(index: number) {
    setJournalForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }));
  }

  function submitAccount() {
    const parsed = accountFormSchema.safeParse(accountForm);
    if (!parsed.success) {
      setAccountErrors(fieldErrors(parsed.error));
      return;
    }
    setAccountErrors({});
    createAccount.mutate(parsed.data, {
      onSuccess: () => {
        setAccountOpen(false);
        setAccountForm(EMPTY_ACCOUNT_FORM);
      },
    });
  }

  function submitJournal() {
    const parsed = journalFormSchema.safeParse(journalForm);
    if (!parsed.success) {
      setJournalErrors(fieldErrors(parsed.error));
      return;
    }
    setJournalErrors({});
    createJournal.mutate(parsed.data, {
      onSuccess: () => {
        setJournalOpen(false);
        setJournalForm(emptyJournalForm());
      },
    });
  }

  const accountColumns: Column<Account>[] = [
    { key: "code", header: "Code", render: (a) => <strong>{a.code}</strong> },
    { key: "name", header: "Name", render: (a) => a.name },
    { key: "type", header: "Type", render: (a) => titleCase(a.account_type) },
    { key: "side", header: "Normal side", render: (a) => titleCase(a.normal_side) },
    {
      key: "flags",
      header: "Flags",
      render: (a) => (
        <span className="table-actions">
          {a.is_cash_or_bank ? <Badge tone="ok">cash/bank</Badge> : null}
          {a.is_system ? <Badge>system</Badge> : null}
        </span>
      ),
    },
  ];

  const journalColumns: Column<JournalEntry>[] = [
    { key: "doc", header: "Doc #", render: (e) => <strong>{e.doc_number}</strong> },
    { key: "date", header: "Date", render: (e) => formatDate(e.entry_date) },
    { key: "description", header: "Description", render: (e) => e.description ?? "—" },
    { key: "source", header: "Source", render: (e) => titleCase(e.source_type) },
    { key: "status", header: "Status", render: (e) => <StatusBadge status={e.status} /> },
    { key: "lines", header: "Lines", align: "right", render: (e) => e.lines.length },
    {
      key: "actions",
      header: "",
      render: (e) => (
        <span className="table-actions">
          <Button variant="secondary" onClick={() => setDetail(e)}>
            View
          </Button>
          {canPost && e.status === "posted" && !e.reversal_of_id ? (
            <Button
              variant="danger"
              onClick={() => reverseJournal.mutate(e.id)}
              disabled={reverseJournal.isPending}
            >
              Reverse
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  const journalLineColumns: Column<JournalLine>[] = [
    { key: "account", header: "Account", render: (l) => `${l.account_code} — ${l.account_name}` },
    { key: "side", header: "Side", render: (l) => titleCase(l.side) },
    { key: "amount", header: "Amount", align: "right", render: (l) => formatMoney(l.amount) },
    { key: "description", header: "Description", render: (l) => l.description ?? "—" },
  ];

  const trialBalanceColumns: Column<TrialBalanceRow>[] = [
    { key: "code", header: "Code", render: (r) => <strong>{r.account_code}</strong> },
    { key: "name", header: "Account", render: (r) => r.account_name },
    { key: "type", header: "Type", render: (r) => titleCase(r.account_type) },
    { key: "debit", header: "Debit", align: "right", render: (r) => formatMoney(r.debit) },
    { key: "credit", header: "Credit", align: "right", render: (r) => formatMoney(r.credit) },
    { key: "balance", header: "Balance", align: "right", render: (r) => formatMoney(r.balance) },
  ];

  const glColumns: Column<GeneralLedgerRow>[] = [
    { key: "doc", header: "Doc #", render: (r) => <strong>{r.doc_number}</strong> },
    { key: "date", header: "Date", render: (r) => formatDate(r.entry_date) },
    { key: "account", header: "Account", render: (r) => `${r.account_code} — ${r.account_name}` },
    { key: "side", header: "Side", render: (r) => titleCase(r.side) },
    { key: "amount", header: "Amount", align: "right", render: (r) => formatMoney(r.amount) },
    { key: "description", header: "Description", render: (r) => r.description ?? "—" },
  ];

  return (
    <>
      <PageHeader
        title="Accounting"
        description="Chart of accounts, journals and financial statements"
      />

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "accounts" ? (
        <>
          <Card
            title="Chart of accounts"
            actions={
              canManageAccounts ? (
                <Button onClick={() => setAccountOpen(true)}>New account</Button>
              ) : null
            }
          >
            <DataTable
              columns={accountColumns}
              rows={accounts.data}
              rowKey={(a) => a.id}
              loading={accounts.isLoading}
              error={accounts.error}
              onRetry={() => accounts.refetch()}
              empty={<EmptyState title="No accounts" message="Seed or create your chart of accounts." />}
            />
          </Card>
        </>
      ) : null}

      {tab === "journals" ? (
        <>
          <Card
            title="Journal entries"
            actions={canPost ? <Button onClick={() => setJournalOpen(true)}>Manual journal</Button> : null}
          >
            <ErrorBanner error={reverseJournal.error} />
            <DataTable
              columns={journalColumns}
              rows={journals.data}
              rowKey={(e) => e.id}
              loading={journals.isLoading}
              error={journals.error}
              onRetry={() => journals.refetch()}
              empty={<EmptyState title="No journal entries" message="Post a manual journal to get started." />}
            />
          </Card>
        </>
      ) : null}

      {tab === "trial-balance" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="From">
                <Input type="date" value={tbFrom} onChange={(event) => setTbFrom(event.target.value)} />
              </Field>
              <Field label="To">
                <Input type="date" value={tbTo} onChange={(event) => setTbTo(event.target.value)} />
              </Field>
            </div>
          </Card>
          <Card title="Trial balance">
            <DataTable
              columns={trialBalanceColumns}
              rows={trialBalance.data}
              rowKey={(r) => r.account_code}
              loading={trialBalance.isLoading}
              error={trialBalance.error}
              onRetry={() => trialBalance.refetch()}
              empty={<EmptyState title="Nothing to show" message="No posted entries in this range." />}
            />
          </Card>
        </>
      ) : null}

      {tab === "pnl" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="From">
                <Input type="date" value={pnlFrom} onChange={(event) => setPnlFrom(event.target.value)} />
              </Field>
              <Field label="To">
                <Input type="date" value={pnlTo} onChange={(event) => setPnlTo(event.target.value)} />
              </Field>
            </div>
          </Card>
          <KpiRow>
            <Kpi label="Income" value={formatMoney(pnl.data?.income)} />
            <Kpi label="Expense" value={formatMoney(pnl.data?.expense)} />
            <Kpi label="Profit" value={formatMoney(pnl.data?.profit)} />
          </KpiRow>
          <ErrorBanner error={pnl.error} />
        </>
      ) : null}

      {tab === "balance-sheet" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="As of">
                <Input
                  type="date"
                  value={bsAsOf}
                  onChange={(event) => setBsAsOf(event.target.value)}
                />
              </Field>
            </div>
          </Card>
          <KpiRow>
            <Kpi label="Assets" value={formatMoney(balanceSheet.data?.assets)} />
            <Kpi label="Liabilities" value={formatMoney(balanceSheet.data?.liabilities)} />
            <Kpi label="Equity" value={formatMoney(balanceSheet.data?.equity_total)} />
            <Kpi
              label="Balanced"
              value={
                balanceSheet.data ? (
                  <StatusBadge status={balanceSheet.data.balanced ? "balanced" : "unbalanced"} />
                ) : (
                  "—"
                )
              }
            />
          </KpiRow>
          <ErrorBanner error={balanceSheet.error} />
        </>
      ) : null}

      {tab === "gl" ? (
        <>
          <Card>
            <div className="form-row">
              <Field label="Account">
                <SheetSelect
                  value={glAccount}
                  options={accountOptions}
                  onChange={setGlAccount}
                  placeholder="All accounts"
                  loading={accounts.isLoading}
                />
              </Field>
              <Field label="From">
                <Input type="date" value={glFrom} onChange={(event) => setGlFrom(event.target.value)} />
              </Field>
              <Field label="To">
                <Input type="date" value={glTo} onChange={(event) => setGlTo(event.target.value)} />
              </Field>
            </div>
          </Card>
          <Card title="General ledger">
            <DataTable
              columns={glColumns}
              rows={generalLedger.data}
              rowKey={(r, index) => `${r.doc_number}-${r.account_code}-${index}`}
              loading={generalLedger.isLoading}
              error={generalLedger.error}
              onRetry={() => generalLedger.refetch()}
              empty={<EmptyState title="No entries" message="No posted lines in this range." />}
            />
          </Card>
        </>
      ) : null}

      <Modal
        open={accountOpen}
        title="New account"
        onClose={() => setAccountOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAccountOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitAccount} disabled={createAccount.isPending}>
              {createAccount.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createAccount.error} />
        <div className="grid-2">
          <Field label="Code" error={accountErrors.code}>
            <Input
              value={accountForm.code}
              onChange={(event) => setAccountForm((prev) => ({ ...prev, code: event.target.value }))}
            />
          </Field>
          <Field label="Name" error={accountErrors.name}>
            <Input
              value={accountForm.name}
              onChange={(event) => setAccountForm((prev) => ({ ...prev, name: event.target.value }))}
            />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Type" error={accountErrors.account_type}>
            <SheetSelect
              value={accountForm.account_type}
              options={ACCOUNT_TYPES.map((t) => ({ value: t, label: titleCase(t) }))}
              onChange={(value) =>
                setAccountForm((prev) => ({
                  ...prev,
                  account_type: value as AccountFormInput["account_type"],
                }))
              }
            />
          </Field>
          <Field label="Normal side" error={accountErrors.normal_side}>
            <SheetSelect
              value={accountForm.normal_side}
              options={SIDES.map((s) => ({ value: s, label: titleCase(s) }))}
              onChange={(value) =>
                setAccountForm((prev) => ({
                  ...prev,
                  normal_side: value as AccountFormInput["normal_side"],
                }))
              }
            />
          </Field>
        </div>
      </Modal>

      <Modal
        open={journalOpen}
        title="Manual journal"
        onClose={() => setJournalOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setJournalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitJournal} disabled={createJournal.isPending || !journalTotals.balanced}>
              {createJournal.isPending ? "Saving…" : "Post"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createJournal.error} />
        <div className="grid-2">
          <Field label="Entry date" error={journalErrors.entry_date}>
            <Input
              type="date"
              value={journalForm.entry_date}
              onChange={(event) =>
                setJournalForm((prev) => ({ ...prev, entry_date: event.target.value }))
              }
            />
          </Field>
          <Field label="Description" error={journalErrors.description}>
            <Input
              value={journalForm.description ?? ""}
              onChange={(event) =>
                setJournalForm((prev) => ({ ...prev, description: event.target.value }))
              }
            />
          </Field>
        </div>

        <div className="card-head" style={{ marginTop: 8 }}>
          <div className="card-title">Lines</div>
          <Button variant="secondary" onClick={addJournalLine}>
            Add line
          </Button>
        </div>
        {journalErrors.lines ? <div className="error-text">{journalErrors.lines}</div> : null}
        {journalForm.lines.map((line, index) => (
          <div key={index} className="grid-3" style={{ alignItems: "end", marginBottom: 8 }}>
            <Field label="Account" error={journalErrors[`lines.${index}.account_code`]}>
              <SheetSelect
                value={line.account_code || null}
                options={accountOptions}
                onChange={(value) => setJournalLine(index, { account_code: value })}
                loading={accounts.isLoading}
              />
            </Field>
            <Field label="Side" error={journalErrors[`lines.${index}.side`]}>
              <SheetSelect
                value={line.side}
                options={SIDES.map((s) => ({ value: s, label: titleCase(s) }))}
                onChange={(value) =>
                  setJournalLine(index, { side: value as JournalLineFormInput["side"] })
                }
              />
            </Field>
            <Field label="Amount" error={journalErrors[`lines.${index}.amount`]}>
              <Input
                value={line.amount}
                onChange={(event) => setJournalLine(index, { amount: event.target.value })}
              />
            </Field>
            <Field label="Description" error={journalErrors[`lines.${index}.description`]}>
              <Input
                value={line.description ?? ""}
                onChange={(event) => setJournalLine(index, { description: event.target.value })}
              />
            </Field>
            <div className="toolbar">
              <Button
                variant="danger"
                onClick={() => removeJournalLine(index)}
                disabled={journalForm.lines.length <= 2}
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
        <div className={journalTotals.balanced ? "muted" : "error-text"}>
          Debits {formatMoney(journalTotals.debit)} · Credits {formatMoney(journalTotals.credit)}
          {journalTotals.balanced ? " · balanced" : " · not balanced"}
        </div>
      </Modal>

      <Sheet
        open={detail !== null}
        title={detail ? `Journal ${detail.doc_number}` : "Journal"}
        onClose={() => setDetail(null)}
      >
        {detail ? (
          <div style={{ padding: 18 }}>
            <div className="grid-2">
              <div>
                <div className="muted">Date</div>
                <div>{formatDate(detail.entry_date)}</div>
              </div>
              <div>
                <div className="muted">Status</div>
                <div>
                  <StatusBadge status={detail.status} />
                </div>
              </div>
              <div>
                <div className="muted">Source</div>
                <div>{titleCase(detail.source_type)}</div>
              </div>
              <div>
                <div className="muted">Description</div>
                <div>{detail.description ?? "—"}</div>
              </div>
            </div>
            <h3 className="card-title" style={{ marginTop: 18 }}>
              Lines
            </h3>
            <DataTable columns={journalLineColumns} rows={detail.lines} rowKey={(l) => l.id} />
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
