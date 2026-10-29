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
  PageHeader,
  Tabs,
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import { FiscalYearsTab } from "./FiscalYearsTab";
import { AppearanceTab } from "./AppearanceTab";
import { PaymentGatewaysTab } from "./PaymentGatewaysTab";
import {
  companiesQueryOptions,
  storageLocationsQueryOptions,
  taxRatesQueryOptions,
  useCreateCompany,
  useCreateStorageLocation,
  useCreateTaxRate,
  useUpdateCompany,
} from "./queries";
import {
  LOCATION_TYPES,
  companyCreateFormSchema,
  companyUpdateFormSchema,
  locationRank,
  storageLocationFormSchema,
  taxRateFormSchema,
  type Company,
  type CompanyCreateFormInput,
  type CompanyUpdateFormInput,
  type LocationType,
  type StorageLocation,
  type StorageLocationFormInput,
  type TaxRate,
  type TaxRateFormInput,
} from "./schemas";

type SettingsTab = "appearance" | "company" | "taxes" | "storage" | "fiscal" | "gateways";

const TABS: { key: SettingsTab; label: string }[] = [
  { key: "appearance", label: "Appearance" },
  { key: "company", label: "Company" },
  { key: "taxes", label: "Tax rates" },
  { key: "storage", label: "Storage locations" },
  { key: "fiscal", label: "Fiscal years & periods" },
  { key: "gateways", label: "Payment gateways" },
];

export function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>("company");
  return (
    <>
      <PageHeader
        title="Settings"
        description="Appearance, company profile, tax rates, storage and fiscal calendars"
      />
      <Tabs tabs={TABS} active={tab} onChange={(key) => setTab(key)} />
      {tab === "appearance" ? <AppearanceTab /> : null}
      {tab === "company" ? <CompanyTab /> : null}
      {tab === "taxes" ? <TaxRatesTab /> : null}
      {tab === "storage" ? <StorageTab /> : null}
      {tab === "fiscal" ? <FiscalYearsTab /> : null}
      {tab === "gateways" ? <PaymentGatewaysTab /> : null}
    </>
  );
}

/* ------------------------------------------------------------------ company */

const EMPTY_COMPANY_CREATE: CompanyCreateFormInput = {
  name: "",
  legal_name: "",
  base_currency: "INR",
  timezone: "UTC",
  locale: "en-IN",
  address: "",
  tax_identifier: "",
};

const EMPTY_COMPANY_UPDATE: CompanyUpdateFormInput = {
  name: "",
  legal_name: "",
  timezone: "UTC",
  locale: "en-IN",
  address: "",
  tax_identifier: "",
  allow_negative_stock: false,
  allow_guest_checkout: false,
  is_active: true,
};

function CompanyTab() {
  const { has } = usePermissions();
  const canCreate = has("platform.users.manage");
  const canEdit = has("company.settings.manage");

  const companies = useQuery(companiesQueryOptions());
  const createCompany = useCreateCompany();
  const updateCompany = useUpdateCompany();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Company | null>(null);
  const [createForm, setCreateForm] = useState<CompanyCreateFormInput>(EMPTY_COMPANY_CREATE);
  const [updateForm, setUpdateForm] = useState<CompanyUpdateFormInput>(EMPTY_COMPANY_UPDATE);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function openCreate() {
    setEditing(null);
    setCreateForm(EMPTY_COMPANY_CREATE);
    setErrors({});
    setOpen(true);
  }

  function openEdit(company: Company) {
    setEditing(company);
    setUpdateForm({
      name: company.name,
      legal_name: company.legal_name,
      timezone: company.timezone,
      locale: company.locale,
      address: company.address ?? "",
      tax_identifier: company.tax_identifier ?? "",
      allow_negative_stock: company.allow_negative_stock,
      allow_guest_checkout: company.allow_guest_checkout,
      is_active: company.is_active,
    });
    setErrors({});
    setOpen(true);
  }

  function submit() {
    if (editing) {
      const parsed = companyUpdateFormSchema.safeParse(updateForm);
      if (!parsed.success) {
        setErrors(fieldErrors(parsed.error));
        return;
      }
      setErrors({});
      updateCompany.mutate({ id: editing.id, input: parsed.data }, { onSuccess: () => setOpen(false) });
      return;
    }
    const parsed = companyCreateFormSchema.safeParse(createForm);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createCompany.mutate(parsed.data, { onSuccess: () => setOpen(false) });
  }

  const columns: Column<Company>[] = [
    { key: "name", header: "Name", render: (c) => <strong>{c.name}</strong> },
    { key: "legal_name", header: "Legal name", render: (c) => c.legal_name || "—" },
    { key: "currency", header: "Currency", render: (c) => c.base_currency },
    { key: "timezone", header: "Timezone", render: (c) => c.timezone },
    {
      key: "status",
      header: "Status",
      render: (c) => <Badge tone={c.is_active ? "ok" : "bad"}>{c.is_active ? "active" : "inactive"}</Badge>,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (c) =>
        canEdit ? (
          <Button variant="secondary" onClick={() => openEdit(c)}>
            Edit
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <Card title="Companies" actions={canCreate ? <Button onClick={openCreate}>New company</Button> : null}>
        <DataTable
          columns={columns}
          rows={companies.data}
          rowKey={(c) => c.id}
          loading={companies.isLoading}
          error={companies.error}
          onRetry={() => companies.refetch()}
          empty={<EmptyState title="No companies" message="Create the first company." />}
        />
      </Card>

      <Modal
        open={open}
        title={editing ? `Edit ${editing.name}` : "New company"}
        onClose={() => setOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createCompany.isPending || updateCompany.isPending}>
              {createCompany.isPending || updateCompany.isPending ? "Saving…" : editing ? "Save" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={editing ? updateCompany.error : createCompany.error} />
        {editing ? (
          <>
            <div className="grid-2">
              <Field label="Name" error={errors.name}>
                <Input
                  value={updateForm.name}
                  onChange={(event) => setUpdateForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </Field>
              <Field label="Legal name" error={errors.legal_name}>
                <Input
                  value={updateForm.legal_name}
                  onChange={(event) =>
                    setUpdateForm((prev) => ({ ...prev, legal_name: event.target.value }))
                  }
                />
              </Field>
            </div>
            <div className="grid-2">
              <Field label="Timezone" error={errors.timezone}>
                <Input
                  value={updateForm.timezone}
                  onChange={(event) => setUpdateForm((prev) => ({ ...prev, timezone: event.target.value }))}
                />
              </Field>
              <Field label="Locale" error={errors.locale}>
                <Input
                  value={updateForm.locale}
                  onChange={(event) => setUpdateForm((prev) => ({ ...prev, locale: event.target.value }))}
                />
              </Field>
            </div>
            <Field label="Tax identifier" error={errors.tax_identifier}>
              <Input
                value={updateForm.tax_identifier}
                onChange={(event) =>
                  setUpdateForm((prev) => ({ ...prev, tax_identifier: event.target.value }))
                }
              />
            </Field>
            <Field label="Address" error={errors.address}>
              <Input
                value={updateForm.address}
                onChange={(event) => setUpdateForm((prev) => ({ ...prev, address: event.target.value }))}
              />
            </Field>
            <div className="toolbar">
              <label className="pill">
                <input
                  type="checkbox"
                  checked={updateForm.allow_negative_stock}
                  onChange={(event) =>
                    setUpdateForm((prev) => ({ ...prev, allow_negative_stock: event.target.checked }))
                  }
                />
                Allow negative stock
              </label>
              <label className="pill">
                <input
                  type="checkbox"
                  checked={updateForm.allow_guest_checkout}
                  onChange={(event) =>
                    setUpdateForm((prev) => ({ ...prev, allow_guest_checkout: event.target.checked }))
                  }
                />
                Allow guest checkout
              </label>
              <label className="pill">
                <input
                  type="checkbox"
                  checked={updateForm.is_active}
                  onChange={(event) =>
                    setUpdateForm((prev) => ({ ...prev, is_active: event.target.checked }))
                  }
                />
                Active
              </label>
            </div>
          </>
        ) : (
          <>
            <div className="grid-2">
              <Field label="Name" error={errors.name}>
                <Input
                  value={createForm.name}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </Field>
              <Field label="Legal name" error={errors.legal_name}>
                <Input
                  value={createForm.legal_name}
                  onChange={(event) =>
                    setCreateForm((prev) => ({ ...prev, legal_name: event.target.value }))
                  }
                />
              </Field>
            </div>
            <div className="grid-3">
              <Field label="Base currency" error={errors.base_currency}>
                <Input
                  value={createForm.base_currency}
                  maxLength={3}
                  onChange={(event) =>
                    setCreateForm((prev) => ({ ...prev, base_currency: event.target.value.toUpperCase() }))
                  }
                />
              </Field>
              <Field label="Timezone" error={errors.timezone}>
                <Input
                  value={createForm.timezone}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, timezone: event.target.value }))}
                />
              </Field>
              <Field label="Locale" error={errors.locale}>
                <Input
                  value={createForm.locale}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, locale: event.target.value }))}
                />
              </Field>
            </div>
            <Field label="Tax identifier" error={errors.tax_identifier}>
              <Input
                value={createForm.tax_identifier}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, tax_identifier: event.target.value }))
                }
              />
            </Field>
            <Field label="Address" error={errors.address}>
              <Input
                value={createForm.address}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, address: event.target.value }))}
              />
            </Field>
          </>
        )}
      </Modal>
    </>
  );
}

/* ---------------------------------------------------------------- tax rates */

const EMPTY_TAX: TaxRateFormInput = {
  code: "",
  name: "",
  percentage: "",
  is_default_sales: false,
  is_default_purchase: false,
};

function TaxRatesTab() {
  const { has } = usePermissions();
  const canManage = has("company.settings.manage");

  const taxes = useQuery(taxRatesQueryOptions());
  const createTax = useCreateTaxRate();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<TaxRateFormInput>(EMPTY_TAX);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function submit() {
    const parsed = taxRateFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createTax.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_TAX);
      },
    });
  }

  const columns: Column<TaxRate>[] = [
    { key: "code", header: "Code", render: (t) => <strong>{t.code}</strong> },
    { key: "name", header: "Name", render: (t) => t.name },
    { key: "percentage", header: "Rate", align: "right", render: (t) => `${t.percentage}%` },
    {
      key: "defaults",
      header: "Defaults",
      render: (t) => (
        <span className="table-actions">
          {t.is_default_sales ? <Badge tone="ok">sales</Badge> : null}
          {t.is_default_purchase ? <Badge>purchase</Badge> : null}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (t) => <Badge tone={t.is_active ? "ok" : "bad"}>{t.is_active ? "active" : "inactive"}</Badge>,
    },
  ];

  return (
    <>
      <Card
        title="Tax rates"
        actions={canManage ? <Button onClick={() => setOpen(true)}>New tax rate</Button> : null}
      >
        <DataTable
          columns={columns}
          rows={taxes.data}
          rowKey={(t) => t.id}
          loading={taxes.isLoading}
          error={taxes.error}
          onRetry={() => taxes.refetch()}
          empty={<EmptyState title="No tax rates" message="Add the tax rates you charge." />}
        />
      </Card>

      <Modal
        open={open}
        title="New tax rate"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createTax.isPending}>
              {createTax.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createTax.error} />
        <div className="grid-2">
          <Field label="Code" error={errors.code}>
            <Input
              value={form.code}
              onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
            />
          </Field>
          <Field label="Name" error={errors.name}>
            <Input
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
          </Field>
        </div>
        <Field label="Percentage" error={errors.percentage}>
          <Input
            value={form.percentage}
            onChange={(event) => setForm((prev) => ({ ...prev, percentage: event.target.value }))}
          />
        </Field>
        <div className="toolbar">
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_default_sales}
              onChange={(event) => setForm((prev) => ({ ...prev, is_default_sales: event.target.checked }))}
            />
            Default for sales
          </label>
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_default_purchase}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, is_default_purchase: event.target.checked }))
              }
            />
            Default for purchasing
          </label>
        </div>
      </Modal>
    </>
  );
}

/* -------------------------------------------------------- storage locations */

const EMPTY_LOCATION: StorageLocationFormInput = {
  code: "",
  name: "",
  location_type: "warehouse",
  parent_id: null,
  address: "",
};

function StorageTab() {
  const { has } = usePermissions();
  const canManage = has("storage.manage");

  const locations = useQuery(storageLocationsQueryOptions());
  const createLocation = useCreateStorageLocation();

  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<StorageLocationFormInput>(EMPTY_LOCATION);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const codeById = useMemo(() => {
    const map = new Map<string, string>();
    for (const location of locations.data ?? []) map.set(location.id, location.code);
    return map;
  }, [locations.data]);

  const rows = useMemo(() => {
    const all = locations.data ?? [];
    return typeFilter ? all.filter((location) => location.location_type === typeFilter) : all;
  }, [locations.data, typeFilter]);

  const parentOptions = useMemo(() => {
    // Only deeper types may become the parent (child rank must be greater).
    const childRank = locationRank(form.location_type);
    return (locations.data ?? [])
      .filter((location) => locationRank(location.location_type) < childRank)
      .map((location) => ({ value: location.id, label: `${location.code} — ${location.name}` }));
  }, [locations.data, form.location_type]);

  const isFacility = locationRank(form.location_type) === 0;

  function submit() {
    const parsed = storageLocationFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createLocation.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_LOCATION);
      },
    });
  }

  const columns: Column<StorageLocation>[] = [
    { key: "code", header: "Code", render: (l) => <strong>{l.code}</strong> },
    { key: "name", header: "Name", render: (l) => l.name },
    { key: "type", header: "Type", render: (l) => titleCase(l.location_type) },
    {
      key: "parent",
      header: "Parent",
      render: (l) => (l.parent_id ? codeById.get(l.parent_id) ?? "—" : "—"),
    },
    {
      key: "status",
      header: "Status",
      render: (l) => <Badge tone={l.is_active ? "ok" : "bad"}>{l.is_active ? "active" : "inactive"}</Badge>,
    },
  ];

  return (
    <>
      <Card
        title="Storage locations"
        actions={canManage ? <Button onClick={() => setOpen(true)}>New location</Button> : null}
      >
        <div className="form-row" style={{ marginBottom: 12 }}>
          <Field label="Type">
            <SheetSelect
              value={typeFilter ?? ""}
              options={[
                { value: "", label: "All types" },
                ...LOCATION_TYPES.map((type) => ({ value: type, label: titleCase(type) })),
              ]}
              onChange={(value) => setTypeFilter(value === "" ? null : value)}
              placeholder="All types"
            />
          </Field>
        </div>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(l) => l.id}
          loading={locations.isLoading}
          error={locations.error}
          onRetry={() => locations.refetch()}
          empty={<EmptyState title="No locations" message="Add a warehouse, godown, or storage bin." />}
        />
      </Card>

      <Modal
        open={open}
        title="New storage location"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createLocation.isPending}>
              {createLocation.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createLocation.error} />
        <div className="grid-2">
          <Field label="Code" error={errors.code}>
            <Input
              value={form.code}
              onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
            />
          </Field>
          <Field label="Name" error={errors.name}>
            <Input
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
          </Field>
        </div>
        <div className="grid-2">
          <Field label="Type" error={errors.location_type}>
            <SheetSelect
              value={form.location_type}
              options={LOCATION_TYPES.map((type) => ({ value: type, label: titleCase(type) }))}
              onChange={(value) =>
                setForm((prev) => {
                  const nextType = value as LocationType;
                  const nextRank = locationRank(nextType);
                  const parentOk =
                    prev.parent_id === null ||
                    (locations.data ?? []).some(
                      (l) => l.id === prev.parent_id && locationRank(l.location_type) < nextRank,
                    );
                  return { ...prev, location_type: nextType, parent_id: parentOk ? prev.parent_id : null };
                })
              }
            />
          </Field>
          {isFacility ? (
            <Field label="Parent location">
              <Input value="— Facilities are top-level —" disabled />
            </Field>
          ) : (
            <Field label="Parent location" error={errors.parent_id}>
              <SheetSelect
                value={form.parent_id ?? ""}
                options={[{ value: "", label: "— No parent —" }, ...parentOptions]}
                onChange={(value) => setForm((prev) => ({ ...prev, parent_id: value === "" ? null : value }))}
                placeholder="No parent"
              />
            </Field>
          )}
        </div>
        <Field label="Address" error={errors.address}>
          <Input
            value={form.address}
            onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
          />
        </Field>
      </Modal>
    </>
  );
}
