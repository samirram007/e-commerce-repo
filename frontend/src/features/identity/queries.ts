import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createRole,
  createUser,
  fetchPermissionCatalog,
  fetchRoles,
  fetchUsers,
  updateUser,
} from "./api";
import type { RoleCreatePayload, UserCreatePayload } from "./schemas";

export const identityKeys = {
  all: ["identity"] as const,
  users: () => [...identityKeys.all, "users"] as const,
  roles: () => [...identityKeys.all, "roles"] as const,
  permissions: () => [...identityKeys.all, "permissions"] as const,
};

export function usersQueryOptions() {
  return queryOptions({
    queryKey: identityKeys.users(),
    queryFn: fetchUsers,
  });
}

export function rolesQueryOptions() {
  return queryOptions({
    queryKey: identityKeys.roles(),
    queryFn: fetchRoles,
  });
}

export function permissionCatalogQueryOptions() {
  return queryOptions({
    queryKey: identityKeys.permissions(),
    queryFn: fetchPermissionCatalog,
    staleTime: 5 * 60_000,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UserCreatePayload) => createUser(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: identityKeys.users() }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Record<string, unknown> }) =>
      updateUser(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: identityKeys.users() }),
  });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RoleCreatePayload) => createRole(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: identityKeys.roles() }),
  });
}
