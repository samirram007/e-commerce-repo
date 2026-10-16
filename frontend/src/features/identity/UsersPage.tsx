import { useState } from "react";
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
  type Column,
} from "../../components/ui";
import { SheetSelect } from "../../components/sheet";
import { usePermissions } from "../../hooks/use-permissions";
import { fieldErrors } from "../../lib/zod-utils";
import { companiesQueryOptions } from "../settings/queries";
import { rolesQueryOptions, usersQueryOptions, useCreateUser, useUpdateUser } from "./queries";
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

export function UsersPage() {
  const { has } = usePermissions();
  const canManage = has("platform.users.manage");

  const users = useQuery(usersQueryOptions());
  const roles = useQuery(rolesQueryOptions());
  const companies = useQuery(companiesQueryOptions());
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [createForm, setCreateForm] = useState<UserCreateFormInput>(EMPTY_CREATE);
  const [updateForm, setUpdateForm] = useState<UserUpdateFormInput>(EMPTY_UPDATE);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function openCreate() {
    setEditing(null);
    setCreateForm(EMPTY_CREATE);
    setErrors({});
    setOpen(true);
  }

  function openEdit(user: User) {
    setEditing(user);
    setUpdateForm({
      full_name: user.full_name,
      password: "",
      is_platform_admin: user.is_platform_admin,
      is_active: user.is_active,
    });
    setErrors({});
    setOpen(true);
  }

  function submit() {
    if (editing) {
      const parsed = userUpdateFormSchema.safeParse(updateForm);
      if (!parsed.success) {
        setErrors(fieldErrors(parsed.error));
        return;
      }
      setErrors({});
      const { full_name, password, is_platform_admin, is_active } = parsed.data;
      const input: Record<string, unknown> = { full_name, is_platform_admin, is_active };
      if (password) input.password = password;
      updateUser.mutate({ id: editing.id, input }, { onSuccess: () => setOpen(false) });
      return;
    }
    const parsed = userCreateFormSchema.safeParse(createForm);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createUser.mutate(parsed.data, { onSuccess: () => setOpen(false) });
  }

  function toggleActive(user: User) {
    updateUser.mutate({ id: user.id, input: { is_active: !user.is_active } });
  }

  const columns: Column<User>[] = [
    { key: "email", header: "Email", render: (u) => <strong>{u.email}</strong> },
    { key: "name", header: "Name", render: (u) => u.full_name || "—" },
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
      render: (u) => <Badge tone={u.is_active ? "ok" : "bad"}>{u.is_active ? "active" : "inactive"}</Badge>,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (u) => (
        <span className="table-actions">
          {canManage ? (
            <Button variant="secondary" onClick={() => openEdit(u)}>
              Edit
            </Button>
          ) : null}
          {canManage ? (
            <Button
              variant={u.is_active ? "danger" : "secondary"}
              disabled={updateUser.isPending}
              onClick={() => toggleActive(u)}
            >
              {u.is_active ? "Deactivate" : "Activate"}
            </Button>
          ) : null}
        </span>
      ),
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
        <DataTable
          columns={columns}
          rows={users.data}
          rowKey={(u) => u.id}
          loading={users.isLoading}
          error={users.error}
          onRetry={() => users.refetch()}
          empty={<EmptyState title="No users" message="Create the first user account." />}
        />
      </Card>

      <Modal
        open={open}
        title={editing ? "Edit user" : "New user"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={submit}
              disabled={createUser.isPending || updateUser.isPending}
            >
              {createUser.isPending || updateUser.isPending
                ? "Saving…"
                : editing
                  ? "Save"
                  : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={editing ? updateUser.error : createUser.error} />
        {editing ? (
          <>
            <Field label="Email">
              <div className="muted">{editing.email}</div>
            </Field>
            <Field label="Full name" error={errors.full_name}>
              <Input
                value={updateForm.full_name}
                onChange={(event) =>
                  setUpdateForm((prev) => ({ ...prev, full_name: event.target.value }))
                }
              />
            </Field>
            <Field
              label="New password"
              error={errors.password}
              hint="Leave blank to keep the current password."
            >
              <Input
                type="password"
                value={updateForm.password}
                onChange={(event) =>
                  setUpdateForm((prev) => ({ ...prev, password: event.target.value }))
                }
              />
            </Field>
            <div className="toolbar">
              <label className="pill">
                <input
                  type="checkbox"
                  checked={updateForm.is_platform_admin}
                  onChange={(event) =>
                    setUpdateForm((prev) => ({ ...prev, is_platform_admin: event.target.checked }))
                  }
                />
                Platform admin
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
            <Field label="Email" error={errors.email}>
              <Input
                type="email"
                value={createForm.email}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, email: event.target.value }))
                }
              />
            </Field>
            <Field label="Full name" error={errors.full_name}>
              <Input
                value={createForm.full_name}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, full_name: event.target.value }))
                }
              />
            </Field>
            <Field label="Password" error={errors.password}>
              <Input
                type="password"
                value={createForm.password}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, password: event.target.value }))
                }
              />
            </Field>
            <div className="toolbar">
              <label className="pill">
                <input
                  type="checkbox"
                  checked={createForm.is_platform_admin}
                  onChange={(event) =>
                    setCreateForm((prev) => ({ ...prev, is_platform_admin: event.target.checked }))
                  }
                />
                Platform admin
              </label>
            </div>
            <Field label="Company membership" hint="Optionally grant the user a role in a company now.">
              <SheetSelect
                value={createForm.company_id}
                options={[
                  { value: "", label: "No company" },
                  ...(companies.data ?? []).map((company) => ({
                    value: company.id,
                    label: company.name,
                  })),
                ]}
                onChange={(value) => setCreateForm((prev) => ({ ...prev, company_id: value }))}
                placeholder="No company"
                title="Select company"
                loading={companies.isLoading}
              />
            </Field>
            {createForm.company_id ? (
              <>
                <Field label="Role">
                  <SheetSelect
                    value={createForm.role_names[0] ?? ""}
                    options={(roles.data ?? []).map((role) => ({
                      value: role.name,
                      label: role.label || role.name,
                    }))}
                    onChange={(value) =>
                      setCreateForm((prev) => ({ ...prev, role_names: value ? [value] : [] }))
                    }
                    placeholder="Select a role"
                    title="Assign role"
                    loading={roles.isLoading}
                  />
                </Field>
                <div className="toolbar">
                  <label className="pill">
                    <input
                      type="checkbox"
                      checked={createForm.is_company_admin}
                      onChange={(event) =>
                        setCreateForm((prev) => ({
                          ...prev,
                          is_company_admin: event.target.checked,
                        }))
                      }
                    />
                    Company admin
                  </label>
                </div>
              </>
            ) : null}
          </>
        )}
      </Modal>
    </>
  );
}
