import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  Modal,
  PageHeader,
  StatusBadge,
  Tabs,
} from "../../components/ui";
import { Sheet, SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { formatMoney, titleCase } from "../../lib/format";
import { fieldErrors } from "../../lib/zod-utils";
import {
  addressesQueryOptions,
  customersQueryOptions,
  useCreateAddress,
  useCreateCustomer,
  useCreateVendor,
  useUpdateCustomer,
  useUpdateVendor,
  vendorsQueryOptions,
} from "./queries";
import {
  ADDRESS_TYPES,
  addressFormSchema,
  type AddressFormInput,
  PARTNER_TYPES,
  type Partner,
  partnerFormSchema,
  type PartnerFormInput,
  partnerUpdateSchema,
  type PartnerType,
} from "./schemas";

const EMPTY_FORM: PartnerFormInput = {
  partner_type: "customer",
  code: "",
  name: "",
  email: "",
  phone: "",
  tax_identifier: "",
  payment_term_days: "0",
  credit_limit: "0",
  is_active: true,
  notes: "",
};

const EMPTY_ADDRESS: AddressFormInput = {
  address_type: "billing",
  line1: "",
  line2: "",
  city: "",
  region: "",
  postal_code: "",
  country: "",
  is_default: false,
};

const PARTNER_TYPE_OPTIONS = PARTNER_TYPES.map((value) => ({
  value,
  label: titleCase(value),
}));
const ADDRESS_TYPE_OPTIONS = ADDRESS_TYPES.map((value) => ({
  value,
  label: titleCase(value),
}));

function formFromPartner(type: PartnerType, partner: Partner): PartnerFormInput {
  return {
    partner_type: type,
    code: partner.code,
    name: partner.name,
    email: partner.email ?? "",
    phone: partner.phone ?? "",
    tax_identifier: partner.tax_identifier ?? "",
    payment_term_days: String(partner.payment_term_days),
    credit_limit: "credit_limit" in partner ? partner.credit_limit : "0",
    is_active: partner.is_active,
    notes: partner.notes ?? "",
  };
}

export function PartnersPage() {
  const { has } = usePermissions();
  const canManage = has("partners.manage");

  const [tab, setTab] = useState<PartnerType>("customer");
  const [search, setSearch] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<{ type: PartnerType; partner: Partner } | null>(null);
  const [form, setForm] = useState<PartnerFormInput>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [selected, setSelected] = useState<{ type: PartnerType; partner: Partner } | null>(null);
  const [addressForm, setAddressForm] = useState<AddressFormInput>(EMPTY_ADDRESS);
  const [addressErrors, setAddressErrors] = useState<Record<string, string>>({});

  const customers = useQuery({
    ...customersQueryOptions(search),
    enabled: tab === "customer",
  });
  const vendors = useQuery({
    ...vendorsQueryOptions(search),
    enabled: tab === "vendor",
  });
  const addresses = useQuery({
    ...addressesQueryOptions(selected?.type ?? "customer", selected?.partner.id ?? ""),
    enabled: selected !== null,
  });

  const createCustomer = useCreateCustomer();
  const updateCustomer = useUpdateCustomer();
  const createVendor = useCreateVendor();
  const updateVendor = useUpdateVendor();
  const createAddress = useCreateAddress();

  const partnerSaving =
    createCustomer.isPending ||
    updateCustomer.isPending ||
    createVendor.isPending ||
    updateVendor.isPending;
  const partnerError =
    createCustomer.error ?? updateCustomer.error ?? createVendor.error ?? updateVendor.error;

  function setField<K extends keyof PartnerFormInput>(key: K, value: PartnerFormInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setAddressField<K extends keyof AddressFormInput>(
    key: K,
    value: AddressFormInput[K],
  ) {
    setAddressForm((prev) => ({ ...prev, [key]: value }));
  }

  function openCreate() {
    setEditing(null);
    setForm({ ...EMPTY_FORM, partner_type: tab });
    setErrors({});
    setModalOpen(true);
  }

  function openEdit(type: PartnerType, partner: Partner) {
    setEditing({ type, partner });
    setForm(formFromPartner(type, partner));
    setErrors({});
    setSelected(null);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
    setForm(EMPTY_FORM);
    setErrors({});
  }

  function submitPartner() {
    const parsed = partnerFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    if (editing) {
      const updated = partnerUpdateSchema.safeParse(form);
      if (!updated.success) {
        setErrors(fieldErrors(updated.error));
        return;
      }
      if (editing.type === "customer") {
        updateCustomer.mutate(
          { id: editing.partner.id, input: updated.data },
          { onSuccess: closeModal },
        );
      } else {
        updateVendor.mutate({ id: editing.partner.id, input: updated.data }, { onSuccess: closeModal });
      }
      return;
    }
    if (parsed.data.partner_type === "customer") {
      createCustomer.mutate(parsed.data, { onSuccess: closeModal });
    } else {
      createVendor.mutate(parsed.data, { onSuccess: closeModal });
    }
  }

  function submitAddress() {
    if (!selected) return;
    const parsed = addressFormSchema.safeParse(addressForm);
    if (!parsed.success) {
      setAddressErrors(fieldErrors(parsed.error));
      return;
    }
    setAddressErrors({});
    createAddress.mutate(
      { partnerType: selected.type, partnerId: selected.partner.id, input: parsed.data },
      { onSuccess: () => setAddressForm(EMPTY_ADDRESS) },
    );
  }

  const rows: Partner[] | undefined = tab === "customer" ? customers.data : vendors.data;
  const list = tab === "customer" ? customers : vendors;

  const columns: Column<Partner>[] = [
    { key: "code", header: "Code", render: (p) => <strong>{p.code}</strong> },
    { key: "name", header: "Name", render: (p) => p.name },
    { key: "email", header: "Email", render: (p) => p.email ?? "—" },
    { key: "phone", header: "Phone", render: (p) => p.phone ?? "—" },
    { key: "terms", header: "Terms", align: "right", render: (p) => `${p.payment_term_days} d` },
    {
      key: "credit",
      header: "Credit limit",
      align: "right",
      render: (p) => ("credit_limit" in p ? formatMoney(p.credit_limit) : "—"),
    },
    { key: "status", header: "Status", render: (p) => <StatusBadge status={p.is_active ? "active" : "inactive"} /> },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <Button variant="secondary" onClick={() => setSelected({ type: tab, partner: p })}>
          View
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Customers & Vendors"
        description="Partner directory, credit terms and address book"
        actions={canManage ? <Button onClick={openCreate}>New {titleCase(tab)}</Button> : null}
      />

      <Card>
        <Tabs
          tabs={[
            { key: "customer", label: "Customers" },
            { key: "vendor", label: "Vendors" },
          ]}
          active={tab}
          onChange={(key) => setTab(key)}
        />
        <div className="form-row">
          <Field label="Search">
            <Input
              value={search}
              placeholder="Code or name"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(p) => p.id}
          loading={list.isLoading}
          error={list.error}
          onRetry={() => list.refetch()}
          empty={
            tab === "customer" ? (
              <EmptyState title="No customers" message="Create your first customer." />
            ) : (
              <EmptyState title="No vendors" message="Create your first vendor." />
            )
          }
        />
      </Card>

      <Modal
        open={modalOpen}
        title={editing ? `Edit ${titleCase(editing.type)}` : "New partner"}
        onClose={closeModal}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={closeModal}>
              Cancel
            </Button>
            <Button onClick={submitPartner} disabled={partnerSaving}>
              {partnerSaving ? "Saving…" : editing ? "Save" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={partnerError} />
        <div className="grid-2">
          <Field label="Type" error={errors.partner_type}>
            <SheetSelect
              value={form.partner_type}
              options={PARTNER_TYPE_OPTIONS}
              onChange={(value) => setField("partner_type", value as PartnerType)}
              disabled={editing !== null}
            />
          </Field>
          <Field label="Code" error={errors.code}>
            <Input
              value={form.code}
              disabled={editing !== null}
              onChange={(event) => setField("code", event.target.value)}
            />
          </Field>
        </div>
        <Field label="Name" error={errors.name}>
          <Input value={form.name} onChange={(event) => setField("name", event.target.value)} />
        </Field>
        <div className="grid-2">
          <Field label="Email" error={errors.email}>
            <Input value={form.email ?? ""} onChange={(event) => setField("email", event.target.value)} />
          </Field>
          <Field label="Phone" error={errors.phone}>
            <Input value={form.phone ?? ""} onChange={(event) => setField("phone", event.target.value)} />
          </Field>
        </div>
        <div className="grid-3">
          <Field label="Tax identifier" error={errors.tax_identifier}>
            <Input
              value={form.tax_identifier ?? ""}
              onChange={(event) => setField("tax_identifier", event.target.value)}
            />
          </Field>
          <Field label="Payment term (days)" error={errors.payment_term_days}>
            <Input
              value={form.payment_term_days}
              onChange={(event) => setField("payment_term_days", event.target.value)}
            />
          </Field>
          <Field label="Credit limit" error={errors.credit_limit}>
            <Input
              value={form.credit_limit}
              disabled={form.partner_type === "vendor"}
              onChange={(event) => setField("credit_limit", event.target.value)}
            />
          </Field>
        </div>
        <Field label="Notes" error={errors.notes}>
          <Input value={form.notes ?? ""} onChange={(event) => setField("notes", event.target.value)} />
        </Field>
        <div className="toolbar">
          <label className="pill">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setField("is_active", event.target.checked)}
            />
            Active
          </label>
        </div>
      </Modal>

      <Sheet
        open={selected !== null}
        title={selected ? selected.partner.name : ""}
        onClose={() => {
          setSelected(null);
          setAddressForm(EMPTY_ADDRESS);
          setAddressErrors({});
        }}
      >
        {selected ? (
          <div className="modal-body" style={{ flex: 1 }}>
            <div className="stack">
              <div className="grid-2">
                <div>
                  <div className="muted">Code</div>
                  <div>{selected.partner.code}</div>
                </div>
                <div>
                  <div className="muted">Type</div>
                  <div>{titleCase(selected.type)}</div>
                </div>
                <div>
                  <div className="muted">Email</div>
                  <div>{selected.partner.email ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Phone</div>
                  <div>{selected.partner.phone ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Tax identifier</div>
                  <div>{selected.partner.tax_identifier ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Payment term</div>
                  <div>{selected.partner.payment_term_days} days</div>
                </div>
                {"credit_limit" in selected.partner ? (
                  <div>
                    <div className="muted">Credit limit</div>
                    <div>{formatMoney(selected.partner.credit_limit)}</div>
                  </div>
                ) : null}
                <div>
                  <div className="muted">Status</div>
                  <StatusBadge status={selected.partner.is_active ? "active" : "inactive"} />
                </div>
              </div>
              {selected.partner.notes ? (
                <div>
                  <div className="muted">Notes</div>
                  <div>{selected.partner.notes}</div>
                </div>
              ) : null}
              <div className="toolbar">
                <Button variant="secondary" onClick={() => openEdit(selected.type, selected.partner)}>
                  Edit
                </Button>
              </div>

              <Card title="Addresses">
                {addresses.isLoading ? (
                  <div className="muted">Loading…</div>
                ) : addresses.data && addresses.data.length > 0 ? (
                  <div className="stack">
                    {addresses.data.map((address) => (
                      <div key={address.id}>
                        <div className="toolbar">
                          <Badge>{titleCase(address.address_type)}</Badge>
                          {address.is_default ? <Badge tone="ok">default</Badge> : null}
                        </div>
                        <div>{address.line1}</div>
                        {address.line2 ? <div>{address.line2}</div> : null}
                        <div className="muted">
                          {[address.city, address.region, address.postal_code, address.country]
                            .filter(Boolean)
                            .join(", ") || "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No addresses" message="Add a billing or shipping address." />
                )}
              </Card>

              <Card title="Add address">
                <ErrorBanner error={createAddress.error} />
                <Field label="Address type" error={addressErrors.address_type}>
                  <SheetSelect
                    value={addressForm.address_type}
                    options={ADDRESS_TYPE_OPTIONS}
                    onChange={(value) =>
                      setAddressField("address_type", value as AddressFormInput["address_type"])
                    }
                  />
                </Field>
                <Field label="Line 1" error={addressErrors.line1}>
                  <Input
                    value={addressForm.line1}
                    onChange={(event) => setAddressField("line1", event.target.value)}
                  />
                </Field>
                <Field label="Line 2" error={addressErrors.line2}>
                  <Input
                    value={addressForm.line2 ?? ""}
                    onChange={(event) => setAddressField("line2", event.target.value)}
                  />
                </Field>
                <div className="grid-2">
                  <Field label="City" error={addressErrors.city}>
                    <Input
                      value={addressForm.city ?? ""}
                      onChange={(event) => setAddressField("city", event.target.value)}
                    />
                  </Field>
                  <Field label="Region" error={addressErrors.region}>
                    <Input
                      value={addressForm.region ?? ""}
                      onChange={(event) => setAddressField("region", event.target.value)}
                    />
                  </Field>
                </div>
                <div className="grid-2">
                  <Field label="Postal code" error={addressErrors.postal_code}>
                    <Input
                      value={addressForm.postal_code ?? ""}
                      onChange={(event) => setAddressField("postal_code", event.target.value)}
                    />
                  </Field>
                  <Field label="Country (ISO2)" error={addressErrors.country}>
                    <Input
                      value={addressForm.country ?? ""}
                      maxLength={2}
                      onChange={(event) => setAddressField("country", event.target.value)}
                    />
                  </Field>
                </div>
                <div className="toolbar">
                  <label className="pill">
                    <input
                      type="checkbox"
                      checked={addressForm.is_default}
                      onChange={(event) => setAddressField("is_default", event.target.checked)}
                    />
                    Default
                  </label>
                  <Button onClick={submitAddress} disabled={createAddress.isPending}>
                    {createAddress.isPending ? "Adding…" : "Add address"}
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
