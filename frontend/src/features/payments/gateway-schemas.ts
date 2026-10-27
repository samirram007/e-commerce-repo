import { z } from "zod";

/**
 * Payment gateway configuration (Setup → Payment gateways).
 *
 * The provider catalog is served by the API (`app/modules/payments/gateways.py`)
 * and the panel renders its forms straight from these field descriptions:
 * credentials, checkout options and any extra key/values the admin adds.
 */
export const credentialFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  secret: z.boolean().optional(),
  required: z.boolean().optional(),
  placeholder: z.string().optional(),
  help: z.string().optional(),
});
export type CredentialField = z.infer<typeof credentialFieldSchema>;

export const settingsFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  type: z.string().optional(),
  options: z.array(z.object({ value: z.string(), label: z.string() })).optional(),
  help: z.string().optional(),
});
export type SettingsField = z.infer<typeof settingsFieldSchema>;

/** A stored gateway setting: a string, a list of instrument codes, or a number. */
export const settingValueSchema = z.union([
  z.string(),
  z.array(z.string()),
  z.number(),
  z.boolean(),
]);

export const gatewaySchema = z.object({
  provider: z.string(),
  label: z.string(),
  display_label: z.string(),
  kind: z.string(),
  /** `ready` has a checkout adapter; `planned` can be configured but not enabled. */
  status: z.string(),
  currencies: z.array(z.string()),
  methods: z.array(z.string()),
  credential_fields: z.array(credentialFieldSchema),
  settings_fields: z.array(settingsFieldSchema),
  capabilities: z.record(z.string(), z.boolean()),
  docs_url: z.string().optional(),
  is_enabled: z.boolean(),
  mode: z.string(),
  priority: z.number(),
  settings: z.record(z.string(), settingValueSchema),
  credential_keys: z.array(z.string()),
  has_credentials: z.boolean(),
  configured: z.boolean(),
  /** Where the credentials in use come from: this company, the deployment, or nowhere. */
  source: z.string(),
  notes: z.string().nullable().optional(),
});
export type Gateway = z.infer<typeof gatewaySchema>;

export const gatewayPageSchema = z.object({
  providers: z.array(z.unknown()),
  gateways: z.array(gatewaySchema),
});
export type GatewayPage = z.infer<typeof gatewayPageSchema>;

export interface GatewayPayload {
  is_enabled?: boolean;
  mode?: string;
  priority?: number;
  label?: string | null;
  credentials?: Record<string, string>;
  settings?: Record<string, unknown>;
}

export const GATEWAY_MODES = ["test", "live"] as const;

export const KIND_LABELS: Record<string, string> = {
  hosted_modal: "Checkout window",
  redirect: "Hosted page redirect",
  offline: "Pay offline",
  sandbox: "Sandbox",
};
