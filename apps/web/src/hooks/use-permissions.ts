import { useAuth } from "../auth/auth-context";

export function hasPermission(permissions: readonly string[] | undefined, needed: string): boolean {
  if (!permissions) return false;
  return permissions.includes("*") || permissions.includes(needed);
}

export interface PermissionsApi {
  permissions: string[];
  roles: string[];
  isPlatformAdmin: boolean;
  isCompanyAdmin: boolean;
  isAdmin: boolean;
  isDeveloper: boolean;
  has: (needed: string) => boolean;
  hasRole: (...roles: string[]) => boolean;
}

/** Reads the auth context's permission/role set (already scoped to the active company). */
export function usePermissions(): PermissionsApi {
  const auth = useAuth();
  return {
    permissions: auth.permissions,
    roles: auth.roles,
    isPlatformAdmin: auth.isPlatformAdmin,
    isCompanyAdmin: auth.isCompanyAdmin,
    isAdmin: auth.isAdmin,
    isDeveloper: auth.isDeveloper,
    has: auth.hasPermission,
    hasRole: auth.hasRole,
  };
}
