import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  PageHeader,
} from "../../components/ui";
import { ServerDataTable, type ServerColumn } from "../../components/data-table";
import { CrudFormModal, useCrudForm } from "../../components/crud-form";
import { SheetSelect } from "../../components/sheet";
import { useListState } from "../../hooks/use-list-state";
import { usePermissions } from "../../hooks/use-permissions";
import { companiesQueryOptions } from "../settings/queries";
import { rolesQueryOptions, useCreateUser, useUpdateUser, usersQueryOptions } from "./queries";
import {
  userCreateFormSchema,
  userUpdateFormSchema,
  type User,
  type UserCreateFormInput,
  type UserUpdateFormInput,
} from "./schemas";

const EMPTY_CREATE: UserCreateFormInput = {
  email: "",
  password: "",
  full_name: "",
  is_platform_admin: false,
  company_id: "",
  role_names: [],
  is_company_admin: false,
};

const EMPTY_UPDATE: UserUpdateFormInput = {
  full_name: "",
  password: "",
  is_platform_admin: false,
  is_active: true,
};

const STATUS_OPTIONS = [
  { value: "", label: "All users" },
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
];

export function UsersPage() {
  const { has } = usePermissions();
  const canManage = has("platform.users.manage");

  // One server-side list state: pagination, sort, debounced search, filters.
  const list = useListState({ sort: "email", order: "asc" });
  const users = useQuery(usersQueryOptions(list.params));
  const roles = useQuery(rolesQueryOptions());
  const companies = useQuery(companiesQueryOptions());

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);

  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const mutationError = createUser.error ?? updateUser.error;

  const form = useCrudForm({
    schema: userCreateFormSchema,
    initialValues: EMPTY_CREATE,
    onSubmit: (values) => {
      createUser.mutate(values, { onSuccess: () => setModalOpen(false) });
    },
  });

  const updateForm = useCrudForm({
    schema: userUpdateFormSchema,
    initialValues: EMPTY_UPDATE,
    onSubmit: (values) => {
      if (!editing) return;
      const { full_name, password, is_platform_admin, is_active } = values;
      const input: Record<string, unknown> = { full_name, is_platform_admin, is_active };
      if (password) input.password = password;
      updateUser.mutate({ id: editing.id, input }, { onSuccess: () => setModalOpen(false) });
    },
  });

  function openCreate() {
    setEditing(null);
    form.reset(EMPTY_CREATE);
    setModalOpen(true);
  }

  function openEdit(user: User) {
    setEditing(user);
    updateForm.reset({
      full_name: user.full_name,
      password: "",
      is_platform_admin: user.is_platform_admin,
      is_active: user.is_active,
    });
    setModalOpen(true);
  }

  function toggleActive(user: User) {
    updateUser.mutate({ id: user.id, input: { is_active: !user.is_active } });
  }

  const roleOptions = useMemo(
    () => [
      { value: "", label: "All roles" },
      ...(roles.data ?? []).map((role) => ({ value: role.name, label: role.label || role.name })),
    ],
    [roles.data],
  );

  const columns: ServerColumn<User>[] = [
    { key: "email", header: "Email", sortKey: "email", render: (u) => <strong>{u.email}</strong> },
    { key: "name", header: "Name", sortKey: "full_name", render: (u) => u.full_name || "—" },
    {
      key: "admin",
      header: "Platform admin",
      render: (u) =>
        u.is_platform_admin ? <Badge tone="warn">admin</Badge> : <span className="muted">—</span>,
    },
    {
      key: "roles",
      header: "Roles",
      render: (u) =>
        u.roles.length > 0 ? (
          <span className="table-actions">
            {u.roles.map((role) => (
              <Badge key={role}>{role.replace(/_/g, " ")}</Badge>
            ))}
          </span>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      sortKey: "is_active",
      render: (u) => <Badge tone={u.is_active ? "ok" : "bad"}>{u.is_active ? "active" : "inactive"}</Badge>,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (u) =>
        canManage ? (
          <span className="table-actions">
            <Button variant="secondary" onClick={() => openEdit(u)}>
              Edit
            </Button>
            <Button
              variant={u.is_active ? "danger" : "secondary"}
              disabled={updateUser.isPending}
              onClick={() => toggleActive(u)}
            >
              {u.is_active ? "Deactivate" : "Activate"}
            </Button>
          </span>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Users"
        description="Platform user accounts"
        actions={canManage ? <Button onClick={openCreate}>New user</Button> : null}
      />

      <Card>
        <ServerDataTable
          columns={columns}
          rows={users.data?.items}
          rowKey={(u) => u.id}
          list={list}
          total={users.data?.total}
          loading={users.isLoading}
          error={users.error}
          onRetry={() => users.refetch()}
          searchPlaceholder="Search name or email…"
          filters={
            <>
              <Field label="Status">
                <SheetSelect
                  value={list.state.filters.is_active ?? ""}
                  options={STATUS_OPTIONS}
                  onChange={(value) => list.setFilter("is_active", value)}
                  placeholder="All users"
                />
              </Field>
              <Field label="Role">
                <SheetSelect
                  value={list.state.filters.role ?? ""}
                  options={roleOptions}
                  onChange={(value) => list.setFilter("role", value)}
                  placeholder="All roles"
                  loading={roles.isLoading}
                />
              </Field>
            </>
          }
          empty={<EmptyState title="No users" message="Create the first user account." />}
        />
      </Card>

      {editing ? (
        <CrudFormModal
          open={modalOpen}
          title={`Edit ${editing.email}`}
          form={updateForm}
          fields={[
            { name: "full_name", label: "Full name" },
            {
              name: "password",
              label: "New password",
              type: "text",
              hint: "Leave blank to keep the current password.",
            },
            { name: "is_platform_admin", label: "Platform admin", type: "checkbox" },
            { name: "is_active", label: "Active", type: "checkbox" },
          ]}
          onClose={() => setModalOpen(false)}
          onSubmit={updateForm.submit}
          submitting={updateUser.isPending}
          error={mutationError}
        />
      ) : (
        <CrudFormModal
          open={modalOpen}
          title="New user"
          form={form}
          fields={[
            { name: "email", label: "Email", placeholder: "user@company.com" },
            { name: "full_name", label: "Full name" },
            { name: "password", label: "Password" },
            { name: "is_platform_admin", label: "Platform admin", type: "checkbox" },
          ]}
          onClose={() => setModalOpen(false)}
          onSubmit={form.submit}
          submitting={createUser.isPending}
          error={mutationError}
          extra={
            <>
              <SheetField
                label="Company membership"
                hint="Optionally grant the user a role in a company now."
                value={form.values.company_id}
                onChange={(value) => form.setValue("company_id", value)}
                options={[
                  { value: "", label: "No company" },
                  ...(companies.data ?? []).map((company) => ({
                    value: company.id,
                    label: company.name,
                  })),
                ]}
                placeholder="No company"
                title="Select company"
                loading={companies.isLoading}
              />
              {form.values.company_id ? (
                <>
                  <SheetField
                    label="Role"
                    value={form.values.role_names[0] ?? ""}
                    onChange={(value) =>
                      form.setValue("role_names", value ? [value] : [])
                    }
                    options={(roles.data ?? []).map((role) => ({
                      value: role.name,
                      label: role.label || role.name,
                    }))}
                    placeholder="Select a role"
                    title="Assign role"
                    loading={roles.isLoading}
                  />
                  <FormCheckbox
                    label="Company admin"
                    checked={form.values.is_company_admin}
                    onChange={(checked) => form.setValue("is_company_admin", checked)}
                  />
                </>
              ) : null}
            </>
          }
        />
      )}
    </>
  );
}

/** Thin wrapper so SheetSelect fits CrudFormModal's `extra` slot. */
function SheetField({
  label,
  hint,
  value,
  onChange,
  options,
  placeholder,
  title,
  loading,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  title?: string;
  loading?: boolean;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <SheetSelect
        value={value}
        options={options}
        onChange={onChange}
        placeholder={placeholder}
        title={title}
        loading={loading}
      />
      {hint ? <div className="muted">{hint}</div> : null}
    </div>
  );
}

function FormCheckbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="field">
      <label className="pill">
        <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
        {label}
      </label>
    </div>
  );
}
