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
  type Column,
} from "../../components/ui";
import { usePermissions } from "../../hooks/use-permissions";
import { fieldErrors } from "../../lib/zod-utils";
import { permissionCatalogQueryOptions, rolesQueryOptions, useCreateRole } from "./queries";
import { roleCreateFormSchema, type Role, type RoleCreateFormInput } from "./schemas";

const EMPTY_ROLE: RoleCreateFormInput = { name: "", permissions: [] };

export function RolesPage() {
  const { has } = usePermissions();
  const canManage = has("platform.users.manage");

  const roles = useQuery(rolesQueryOptions());
  const catalog = useQuery(permissionCatalogQueryOptions());
  const createRole = useCreateRole();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<RoleCreateFormInput>(EMPTY_ROLE);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const grouped = useMemo(() => {
    const groups = new Map<string, { key: string; label: string }[]>();
    for (const [key, label] of Object.entries(catalog.data?.permissions ?? {})) {
      const area = key.split(".")[0] ?? "other";
      const list = groups.get(area) ?? [];
      list.push({ key, label });
      groups.set(area, list);
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [catalog.data]);

  function togglePermission(key: string) {
    setForm((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(key)
        ? prev.permissions.filter((value) => value !== key)
        : [...prev.permissions, key],
    }));
  }

  function submit() {
    const parsed = roleCreateFormSchema.safeParse(form);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    createRole.mutate(parsed.data, {
      onSuccess: () => {
        setOpen(false);
        setForm(EMPTY_ROLE);
      },
    });
  }

  const columns: Column<Role>[] = [
    {
      key: "name",
      header: "Role",
      render: (r) => (
        <div>
          <strong>{r.label || r.name}</strong>
          {r.label ? <div className="muted">{r.name}</div> : null}
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (r) => (r.is_system ? <Badge tone="warn">system</Badge> : <Badge>custom</Badge>),
    },
    {
      key: "permissions",
      header: "Permissions",
      render: (r) => (
        <span className="table-actions">
          {r.permissions.length === 0 ? (
            <span className="muted">none</span>
          ) : (
            r.permissions.map((permission) => <Badge key={permission}>{permission}</Badge>)
          )}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Roles"
        description="Permission bundles granted to company members"
        actions={canManage ? <Button onClick={() => setOpen(true)}>New role</Button> : null}
      />

      <Card>
        <DataTable
          columns={columns}
          rows={roles.data}
          rowKey={(r) => r.id}
          loading={roles.isLoading}
          error={roles.error}
          onRetry={() => roles.refetch()}
          empty={<EmptyState title="No roles" message="Create a role to group permissions." />}
        />
      </Card>

      <Modal
        open={open}
        title="New role"
        onClose={() => setOpen(false)}
        wide
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={createRole.isPending}>
              {createRole.isPending ? "Saving…" : "Create"}
            </Button>
          </>
        }
      >
        <ErrorBanner error={createRole.error} />
        <Field label="Role name" error={errors.name}>
          <Input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
          />
        </Field>
        {errors.permissions ? (
          <div className="error-text" style={{ marginBottom: 8 }}>
            {errors.permissions}
          </div>
        ) : (
          <div className="muted" style={{ marginBottom: 8 }}>
            Pick the permissions this role should grant.
          </div>
        )}
        {catalog.isLoading ? <div className="muted">Loading permissions…</div> : null}
        {grouped.map(([area, permissions]) => (
          <div key={area} style={{ marginBottom: 12 }}>
            <div className="subtle" style={{ textTransform: "capitalize", marginBottom: 4 }}>
              {area}
            </div>
            <div className="toolbar">
              {permissions.map((permission) => (
                <label className="pill" key={permission.key}>
                  <input
                    type="checkbox"
                    checked={form.permissions.includes(permission.key)}
                    onChange={() => togglePermission(permission.key)}
                  />
                  {permission.label}
                </label>
              ))}
            </div>
          </div>
        ))}
      </Modal>
    </>
  );
}
