import { api } from "../../lib/api-client";
import {
  permissionCatalogSchema,
  roleListSchema,
  roleSchema,
  userListSchema,
  userSchema,
  type PermissionCatalog,
  type Role,
  type RoleCreatePayload,
  type User,
  type UserCreatePayload,
} from "./schemas";

/**
 * Identity transport for users/roles/permission catalog. Authentication
 * (login/bootstrap/me/logout/refresh) is owned by `services/identity-helpers`.
 */

export async function fetchUsers(): Promise<User[]> {
  const { data } = await api.get("/users");
  return userListSchema.parse(data);
}

export async function createUser(input: UserCreatePayload): Promise<User> {
  const { data } = await api.post("/users", input);
  return userSchema.parse(data);
}

export async function updateUser(id: string, input: Record<string, unknown>): Promise<User> {
  const { data } = await api.patch(`/users/${id}`, input);
  return userSchema.parse(data);
}

export async function fetchRoles(): Promise<Role[]> {
  const { data } = await api.get("/roles");
  return roleListSchema.parse(data);
}

export async function createRole(input: RoleCreatePayload): Promise<Role> {
  const { data } = await api.post("/roles", input);
  return roleSchema.parse(data);
}

export async function fetchPermissionCatalog(): Promise<PermissionCatalog> {
  const { data } = await api.get("/auth/permissions");
  return permissionCatalogSchema.parse(data);
}
