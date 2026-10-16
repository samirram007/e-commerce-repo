import { z } from "zod";

/* ---- auth (LoginPage) ---- */
export const loginFormSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
export type LoginFormInput = z.input<typeof loginFormSchema>;

export const bootstrapFormSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters"),
  full_name: z.string().trim().max(200, "Too long"),
});
export type BootstrapFormInput = z.input<typeof bootstrapFormSchema>;

/* ---- users ---- */
export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string(),
  is_platform_admin: z.boolean(),
  is_active: z.boolean(),
  roles: z.array(z.string()).default([]),
});
export type User = z.infer<typeof userSchema>;

export const userListSchema = z.array(userSchema);

export const userCreateFormSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Use at least 8 characters"),
  full_name: z.string().trim().max(200, "Too long"),
  is_platform_admin: z.boolean(),
  /** Optional single-step membership: which company + which role to grant. */
  company_id: z.string(),
  role_names: z.array(z.string()),
  is_company_admin: z.boolean(),
});
export type UserCreateFormInput = z.input<typeof userCreateFormSchema>;
export type UserCreatePayload = z.output<typeof userCreateFormSchema>;

export const userUpdateFormSchema = z.object({
  full_name: z.string().trim().max(200, "Too long"),
  password: z
    .string()
    .refine((value) => value === "" || value.length >= 8, "Use at least 8 characters"),
  is_platform_admin: z.boolean(),
  is_active: z.boolean(),
});
export type UserUpdateFormInput = z.input<typeof userUpdateFormSchema>;

/* ---- roles ---- */
export const roleSchema = z.object({
  id: z.string(),
  name: z.string(),
  label: z.string().default(""),
  permissions: z.array(z.string()),
  is_system: z.boolean(),
});
export type Role = z.infer<typeof roleSchema>;

export const roleListSchema = z.array(roleSchema);

export const roleCreateFormSchema = z.object({
  name: z.string().trim().min(2, "Use at least 2 characters").max(64, "Too long"),
  permissions: z.array(z.string()).min(1, "Select at least one permission"),
});
export type RoleCreateFormInput = z.input<typeof roleCreateFormSchema>;
export type RoleCreatePayload = z.output<typeof roleCreateFormSchema>;

/** Assignable user tiers surfaced first in pickers. */
export const USER_TIER_ROLES = ["developer", "admin", "other_user"] as const;

/* ---- permission catalogue (GET /auth/permissions) ---- */
export const permissionCatalogSchema = z.object({
  permissions: z.record(z.string(), z.string()),
  roles: z.array(z.string()),
});
export type PermissionCatalog = z.infer<typeof permissionCatalogSchema>;
