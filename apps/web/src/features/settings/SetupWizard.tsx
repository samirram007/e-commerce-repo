import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
} from "../../components/ui";
import { usePermissions } from "../../hooks/use-permissions";
import { useAuth } from "../../auth/auth-context";
import { formatDate } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { accountsQueryOptions, useSeedDefaultAccounts } from "../accounting/queries";
import {
  companiesQueryOptions,
  fiscalYearsQueryOptions,
  useCreateCompany,
  useCreateFiscalYear,
  useUpdateCompany,
} from "./queries";
import {
  companyCreateFormSchema,
  companyUpdateFormSchema,
  fiscalYearFormSchema,
  type CompanyCreateFormInput,
  type CompanyUpdateFormInput,
  type FiscalYearFormInput,
} from "./schemas";

type Step = "company" | "fiscal" | "chart";

const STEPS: { key: Step; label: string; title: string }[] = [
  { key: "company", label: "1. Company", title: "Company profile" },
  { key: "fiscal", label: "2. Fiscal year", title: "Fiscal year" },
  { key: "chart", label: "3. Chart of accounts", title: "Chart of accounts" },
];

const EMPTY_COMPANY_CREATE: CompanyCreateFormInput = {
  name: "",
  legal_name: "",
  base_currency: "INR",
  timezone: "UTC",
  locale: "en-IN",
  address: "",
  tax_identifier: "",
};

const EMPTY_FISCAL: FiscalYearFormInput = { name: "", start_date: "", end_date: "" };

function currentYearRange(): FiscalYearFormInput {
  const year = new Date().getFullYear();
  return { name: `FY${year}`, start_date: `${year}-01-01`, end_date: `${year}-12-31` };
}

/**
 * Guided first-run setup: company profile → fiscal year → chart of accounts.
 * Each step reports whether it is already done (green) so a partially
 * configured company can pick up where it left off; every action calls the
 * same endpoints as Settings, this only orders them.
 */
export function SetupWizard() {
  const { has } = usePermissions();
  const { companyId } = useAuth();
  const canManageCompany = has("company.settings.manage");
  const canCreateCompany = has("platform.users.manage");
  const canManageFiscal = has("fiscal.manage");
  const canManageAccounts = has("accounting.accounts.manage");

  const [step, setStep] = useState<Step>("company");
  const [done, setDone] = useState<Record<Step, boolean>>({
    company: false,
    fiscal: false,
    chart: false,
  });

  const companies = useQuery(companiesQueryOptions());
  const fiscalYears = useQuery(fiscalYearsQueryOptions());
  const accounts = useQuery(accountsQueryOptions());

  const activeCompany = useMemo(
    () => companies.data?.find((c) => c.id === companyId) ?? companies.data?.[0] ?? null,
    [companies.data, companyId],
  );

  // Editing the active company vs. creating the first one.
  const isCompanyConfigured = Boolean(activeCompany);
  const [companyForm, setCompanyForm] = useState<CompanyCreateFormInput>(EMPTY_COMPANY_CREATE);
  const [companyUpdate, setCompanyUpdate] = useState<CompanyUpdateFormInput | null>(null);
  const [companyErrors, setCompanyErrors] = useState<Record<string, string>>({});
  const createCompany = useCreateCompany();
  const updateCompany = useUpdateCompany();

  // Fiscal year step.
  const hasFiscalYear = (fiscalYears.data ?? []).length > 0;
  const [fiscalForm, setFiscalForm] = useState<FiscalYearFormInput>(EMPTY_FISCAL);
  const [fiscalErrors, setFiscalErrors] = useState<Record<string, string>>({});
  const createFiscalYear = useCreateFiscalYear();

  // Chart step.
  const accountCount = (accounts.data ?? []).length;
  const seedChart = useSeedDefaultAccounts();

  function openCompanyStep() {
    if (activeCompany && !companyUpdate) {
      setCompanyUpdate({
        name: activeCompany.name,
        legal_name: activeCompany.legal_name,
        timezone: activeCompany.timezone,
        locale: activeCompany.locale,
        address: activeCompany.address ?? "",
        tax_identifier: activeCompany.tax_identifier ?? "",
        allow_negative_stock: activeCompany.allow_negative_stock,
        allow_guest_checkout: activeCompany.allow_guest_checkout,
        is_active: activeCompany.is_active,
      });
    }
    if (!hasFiscalYear && fiscalForm.start_date === "") {
      setFiscalForm(currentYearRange());
    }
  }

  function submitCompany() {
    if (isCompanyConfigured && companyUpdate) {
      const parsed = companyUpdateFormSchema.safeParse(companyUpdate);
      if (!parsed.success) {
        setCompanyErrors(fieldErrors(parsed.error));
        return;
      }
      setCompanyErrors({});
      updateCompany.mutate(
        { id: activeCompany!.id, input: parsed.data },
        {
          onSuccess: () => {
            setDone((prev) => ({ ...prev, company: true }));
            setStep("fiscal");
          },
        },
      );
      return;
    }
    const parsed = companyCreateFormSchema.safeParse(companyForm);
    if (!parsed.success) {
      setCompanyErrors(fieldErrors(parsed.error));
      return;
    }
    setCompanyErrors({});
    createCompany.mutate(parsed.data, {
      onSuccess: () => {
        void companies.refetch();
        setDone((prev) => ({ ...prev, company: true }));
        setStep("fiscal");
      },
    });
  }

  function submitFiscal() {
    const parsed = fiscalYearFormSchema.safeParse(fiscalForm);
    if (!parsed.success) {
      setFiscalErrors(fieldErrors(parsed.error));
      return;
    }
    setFiscalErrors({});
    createFiscalYear.mutate(parsed.data, {
      onSuccess: () => {
        void fiscalYears.refetch();
        setDone((prev) => ({ ...prev, fiscal: true }));
        setStep("chart");
      },
    });
  }

  function submitChart() {
    seedChart.mutate(undefined, {
      onSuccess: (rows) => {
        setDone((prev) => ({ ...prev, chart: rows.length > 0 }));
      },
    });
  }

  const stepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <>
      <PageHeader
        title="Company setup"
        description="Three steps: company profile, fiscal year, chart of accounts"
      />

      <div className="tabs" style={{ marginBottom: 16 }}>
        {STEPS.map((s) => (
          <button
            key={s.key}
            type="button"
            className={s.key === step ? "tab active" : "tab"}
            onClick={() => {
              setStep(s.key);
              if (s.key === "company") openCompanyStep();
            }}
          >
            {s.label}
            {done[s.key] || (s.key === "fiscal" && hasFiscalYear) || (s.key === "chart" && accountCount > 0)
              ? " ✓"
              : ""}
          </button>
        ))}
      </div>

      {/* ------------------------------------------------------- company */}
      {step === "company" ? (
        <Card title="Company profile">
          <ErrorBanner error={createCompany.error ?? updateCompany.error} />
          {!canManageCompany && !canCreateCompany ? (
            <p className="muted">
              You need company settings permission to configure the company profile.
            </p>
          ) : isCompanyConfigured ? (
            <>
              <p className="muted">
                Active company: <strong>{activeCompany?.name}</strong> ({activeCompany?.base_currency})
              </p>
              {companyUpdate ? (
                <>
                  <div className="grid-2">
                    <Field label="Name" error={companyErrors.name}>
                      <Input
                        value={companyUpdate.name}
                        onChange={(event) =>
                          setCompanyUpdate((prev) =>
                            prev ? { ...prev, name: event.target.value } : prev,
                          )
                        }
                      />
                    </Field>
                    <Field label="Legal name" error={companyErrors.legal_name}>
                      <Input
                        value={companyUpdate.legal_name}
                        onChange={(event) =>
                          setCompanyUpdate((prev) =>
                            prev ? { ...prev, legal_name: event.target.value } : prev,
                          )
                        }
                      />
                    </Field>
                  </div>
                  <div className="grid-2">
                    <Field label="Timezone" error={companyErrors.timezone}>
                      <Input
                        value={companyUpdate.timezone}
                        onChange={(event) =>
                          setCompanyUpdate((prev) =>
                            prev ? { ...prev, timezone: event.target.value } : prev,
                          )
                        }
                      />
                    </Field>
                    <Field label="Locale" error={companyErrors.locale}>
                      <Input
                        value={companyUpdate.locale}
                        onChange={(event) =>
                          setCompanyUpdate((prev) =>
                            prev ? { ...prev, locale: event.target.value } : prev,
                          )
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Address" error={companyErrors.address}>
                    <Input
                      value={companyUpdate.address}
                      onChange={(event) =>
                        setCompanyUpdate((prev) =>
                          prev ? { ...prev, address: event.target.value } : prev,
                        )
                      }
                    />
                  </Field>
                  <Field label="Tax identifier" error={companyErrors.tax_identifier}>
                    <Input
                      value={companyUpdate.tax_identifier}
                      onChange={(event) =>
                        setCompanyUpdate((prev) =>
                          prev ? { ...prev, tax_identifier: event.target.value } : prev,
                        )
                      }
                    />
                  </Field>
                </>
              ) : (
                <p className="muted">Loading…</p>
              )}
            </>
          ) : (
            <>
              <p className="muted">No company yet — create the first one.</p>
              <div className="grid-2">
                <Field label="Name" error={companyErrors.name}>
                  <Input
                    value={companyForm.name}
                    onChange={(event) =>
                      setCompanyForm((prev) => ({ ...prev, name: event.target.value }))
                    }
                  />
                </Field>
                <Field label="Legal name" error={companyErrors.legal_name}>
                  <Input
                    value={companyForm.legal_name}
                    onChange={(event) =>
                      setCompanyForm((prev) => ({ ...prev, legal_name: event.target.value }))
                    }
                  />
                </Field>
              </div>
              <div className="grid-3">
                <Field label="Base currency" error={companyErrors.base_currency}>
                  <Input
                    value={companyForm.base_currency}
                    maxLength={3}
                    onChange={(event) =>
                      setCompanyForm((prev) => ({
                        ...prev,
                        base_currency: event.target.value.toUpperCase(),
                      }))
                    }
                  />
                </Field>
                <Field label="Timezone" error={companyErrors.timezone}>
                  <Input
                    value={companyForm.timezone}
                    onChange={(event) =>
                      setCompanyForm((prev) => ({ ...prev, timezone: event.target.value }))
                    }
                  />
                </Field>
                <Field label="Locale" error={companyErrors.locale}>
                  <Input
                    value={companyForm.locale}
                    onChange={(event) =>
                      setCompanyForm((prev) => ({ ...prev, locale: event.target.value }))
                    }
                  />
                </Field>
              </div>
            </>
          )}
          <div className="toolbar" style={{ marginTop: 12 }}>
            <Button
              onClick={submitCompany}
              disabled={createCompany.isPending || updateCompany.isPending}
            >
              {createCompany.isPending || updateCompany.isPending
                ? "Saving…"
                : isCompanyConfigured
                  ? "Save & continue"
                  : "Create company & continue"}
            </Button>
            <Button variant="secondary" onClick={() => setStep("fiscal")}>
              Skip
            </Button>
          </div>
        </Card>
      ) : null}

      {/* ------------------------------------------------------- fiscal */}
      {step === "fiscal" ? (
        <Card title="Fiscal year">
          <ErrorBanner error={createFiscalYear.error} />
          {hasFiscalYear ? (
            <>
              <p className="muted">
                <Badge tone="ok">configured</Badge> {(fiscalYears.data ?? []).length} fiscal
                year(s) defined. Latest:{" "}
                {(fiscalYears.data ?? []).map((fy) => fy.name).join(", ")}
              </p>
              <div className="toolbar" style={{ marginTop: 12 }}>
                <Button variant="secondary" onClick={() => setStep("chart")}>
                  Continue
                </Button>
              </div>
            </>
          ) : (
            <>
              {!canManageFiscal ? (
                <p className="muted">You need fiscal.manage permission to create fiscal years.</p>
              ) : null}
              <Field label="Name" error={fiscalErrors.name} hint="Defaults to the date range.">
                <Input
                  value={fiscalForm.name}
                  placeholder="FY2026"
                  onChange={(event) =>
                    setFiscalForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                />
              </Field>
              <div className="grid-2">
                <Field label="Start date" error={fiscalErrors.start_date}>
                  <Input
                    type="date"
                    value={fiscalForm.start_date}
                    onChange={(event) =>
                      setFiscalForm((prev) => ({ ...prev, start_date: event.target.value }))
                    }
                  />
                </Field>
                <Field label="End date" error={fiscalErrors.end_date}>
                  <Input
                    type="date"
                    value={fiscalForm.end_date}
                    onChange={(event) =>
                      setFiscalForm((prev) => ({ ...prev, end_date: event.target.value }))
                    }
                  />
                </Field>
              </div>
              <div className="toolbar" style={{ marginTop: 12 }}>
                <Button onClick={submitFiscal} disabled={createFiscalYear.isPending}>
                  {createFiscalYear.isPending ? "Saving…" : "Create fiscal year & continue"}
                </Button>
                <Button variant="secondary" onClick={() => setStep("chart")}>
                  Skip
                </Button>
              </div>
            </>
          )}
        </Card>
      ) : null}

      {/* -------------------------------------------------------- chart */}
      {step === "chart" ? (
        <Card title="Chart of accounts">
          <ErrorBanner error={seedChart.error} />
          {accountCount > 0 ? (
            <p className="muted">
              <Badge tone="ok">configured</Badge> {accountCount} accounts in the chart. Manage
              them on the Accounting screen.
            </p>
          ) : (
            <>
              <p className="muted">
                No accounts yet. Seed the standard chart (assets, liabilities, equity, income,
                expenses) — it is idempotent and fills only missing accounts.
              </p>
              {!canManageAccounts ? (
                <p className="muted">You need accounting.accounts.manage permission.</p>
              ) : null}
            </>
          )}
          <div className="toolbar" style={{ marginTop: 12 }}>
            <Button
              onClick={submitChart}
              disabled={seedChart.isPending || !canManageAccounts}
            >
              {seedChart.isPending
                ? "Seeding…"
                : accountCount > 0
                  ? "Check for missing accounts"
                  : "Seed default chart"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                const next = STEPS[(stepIndex + 1) % STEPS.length];
                setStep(next.key);
              }}
            >
              Back to start
            </Button>
          </div>
          {accountCount > 0 ? (
            <p className="muted" style={{ marginTop: 12 }}>
              Setup complete — {hasFiscalYear ? "your fiscal year and chart are ready" : "create a fiscal year before posting"}.{" "}
              {fiscalYears.data?.[0]
                ? `Latest year: ${fiscalYears.data[0].name} (${formatDate(fiscalYears.data[0].start_date)} → ${formatDate(fiscalYears.data[0].end_date)}).`
                : ""}
            </p>
          ) : null}
        </Card>
      ) : null}
    </>
  );
}
