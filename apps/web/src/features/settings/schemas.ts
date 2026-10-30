import { z } from "zod";
import {
  FACILITY_TYPES,
  LOCATION_TYPES,
  STOCKABLE_TYPES,
  isFacilityType,
  isStockableType,
  locationRank,
  type LocationType,
} from "../../lib/location-types";

/** Money/percent values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

/* ---- company ---- */
export const companySchema = z.object({
  id: z.string(),
  name: z.string(),
  legal_name: z.string(),
  base_currency: z.string(),
  timezone: z.string(),
  locale: z.string(),
  address: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  allow_negative_stock: z.boolean(),
  allow_guest_checkout: z.boolean(),
  is_active: z.boolean(),
  storefront_slug: z.string().nullable().optional(),
});
export type Company = z.infer<typeof companySchema>;

export const companyListSchema = z.array(companySchema);

export const companyAddressOutSchema = z.object({
  id: z.string(),
  address_type: z.string(),
  line1: z.string(),
  line2: z.string().nullable(),
  city: z.string(),
  region: z.string().nullable(),
  postal_code: z.string().nullable(),
  country: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  is_default: z.boolean(),
});
export type CompanyAddressOut = z.infer<typeof companyAddressOutSchema>;

export const companyAddressInSchema = z.object({
  address_type: z.string().min(1, "Address type is required"),
  line1: z.string().min(1, "Line 1 is required"),
  line2: z.string().nullable(),
  city: z.string().min(1, "City is required"),
  region: z.string().nullable(),
  postal_code: z.string().nullable(),
  country: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  is_default: z.boolean().default(false),
});
export type CompanyAddressIn = z.infer<typeof companyAddressInSchema>;

/* ---- tax rates ---- */

export const companyCreateFormSchema = z.object({
  name: z.string().trim().min(2, "Use at least 2 characters").max(200, "Too long"),
  legal_name: z.string().trim().max(200, "Too long"),
  base_currency: z.string().trim().length(3, "Use a 3-letter code"),
  timezone: z.string().trim().min(1, "Required").max(64, "Too long"),
  locale: z.string().trim().min(1, "Required").max(16, "Too long"),
  address: z.string().trim().max(500, "Too long"),
  tax_identifier: z.string().trim().max(64, "Too long"),
  storefront_slug: z.string().trim().max(50, "Too long").optional(),
});
export type CompanyCreateFormInput = z.input<typeof companyCreateFormSchema>;
export type CompanyCreatePayload = z.output<typeof companyCreateFormSchema>;

export const companyUpdateFormSchema = z.object({
  name: z.string().trim().min(2, "Use at least 2 characters").max(200, "Too long"),
  legal_name: z.string().trim().max(200, "Too long"),
  timezone: z.string().trim().min(1, "Required").max(64, "Too long"),
  locale: z.string().trim().min(1, "Required").max(16, "Too long"),
  address: z.string().trim().max(500, "Too long"),
  tax_identifier: z.string().trim().max(64, "Too long"),
  allow_negative_stock: z.boolean(),
  allow_guest_checkout: z.boolean(),
  is_active: z.boolean(),
  storefront_slug: z.string().trim().max(50, "Too long").optional(),
});
export type CompanyUpdateFormInput = z.input<typeof companyUpdateFormSchema>;
export type CompanyUpdatePayload = z.output<typeof companyUpdateFormSchema>;

/* ---- tax rates ---- */
export const taxRateSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  percentage: decimalString,
  is_default_sales: z.boolean(),
  is_default_purchase: z.boolean(),
  is_active: z.boolean(),
});
export type TaxRate = z.infer<typeof taxRateSchema>;

export const taxRateListSchema = z.array(taxRateSchema);

const percentageInput = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid percentage")
  .refine((value) => Number(value) >= 0 && Number(value) <= 100, "Must be between 0 and 100")
  .transform((value) => Number(value));

export const taxRateFormSchema = z.object({
  code: z.string().trim().min(1, "Required").max(32, "Too long"),
  name: z.string().trim().min(1, "Required").max(100, "Too long"),
  percentage: percentageInput,
  is_default_sales: z.boolean(),
  is_default_purchase: z.boolean(),
});
export type TaxRateFormInput = z.input<typeof taxRateFormSchema>;
export type TaxRatePayload = z.output<typeof taxRateFormSchema>;

/* ---- storage locations ---- */
export { LOCATION_TYPES, FACILITY_TYPES, STOCKABLE_TYPES, isFacilityType, isStockableType, locationRank };
export type { LocationType };

export const storageLocationSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  location_type: z.string(),
  parent_id: z.string().nullable(),
  address: z.string().nullable(),
  is_active: z.boolean(),
});
export type StorageLocation = z.infer<typeof storageLocationSchema>;

export const storageLocationListSchema = z.array(storageLocationSchema);

export const storageLocationFormSchema = z.object({
  code: z.string().trim().min(1, "Required").max(64, "Too long"),
  name: z.string().trim().min(1, "Required").max(200, "Too long"),
  location_type: z.enum(LOCATION_TYPES),
  parent_id: z.string().nullable(),
  address: z.string().trim().max(500, "Too long"),
});
export type StorageLocationFormInput = z.input<typeof storageLocationFormSchema>;
export type StorageLocationPayload = z.output<typeof storageLocationFormSchema>;

/* ---- fiscal years ---- */
export const fiscalYearSchema = z.object({
  id: z.string(),
  name: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  is_open: z.boolean(),
});
export type FiscalYear = z.infer<typeof fiscalYearSchema>;

export const fiscalYearListSchema = z.array(fiscalYearSchema);

/** Monthly accounting period under a fiscal year (`GET /fiscal-years/{id}/periods`). */
export const fiscalYearPeriodSchema = z.object({
  id: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  is_open: z.boolean(),
});
export type FiscalYearPeriod = z.infer<typeof fiscalYearPeriodSchema>;
export const fiscalYearPeriodListSchema = z.array(fiscalYearPeriodSchema);

export const closeFiscalYearResultSchema = z.object({
  id: z.string(),
  is_open: z.boolean(),
  closing_entry_id: z.string().nullable(),
  periods_closed: z.boolean(),
});
export type CloseFiscalYearResult = z.infer<typeof closeFiscalYearResultSchema>;

export const forwardFiscalYearResultSchema = z.object({
  from_fiscal_year_id: z.string(),
  to_fiscal_year_id: z.string(),
  to_created: z.boolean(),
  journal_entry_id: z.string(),
  doc_number: z.string(),
  accounts_carried: z.number(),
});
export type ForwardFiscalYearResult = z.infer<typeof forwardFiscalYearResultSchema>;

export const openingBalancesResultSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  entry_date: z.string(),
  fiscal_year_id: z.string().nullable(),
  status: z.string(),
});
export type OpeningBalancesResult = z.infer<typeof openingBalancesResultSchema>;

export const openingBalancesPayloadSchema = z.object({
  entry_date: z.string().nullable().optional(),
  description: z.string().max(200).optional(),
  lines: z
    .array(
      z.object({
        account_code: z.string().min(1, "Account is required"),
        side: z.enum(["debit", "credit"]),
        amount: z.union([z.string(), z.number()]).transform((value) => String(value)),
        description: z.string().max(200).optional(),
      }),
    )
    .min(2, "Opening balances need at least two lines"),
});
export type OpeningBalancesPayload = z.output<typeof openingBalancesPayloadSchema>;
export type OpeningBalancesFormInput = z.input<typeof openingBalancesPayloadSchema>;

export const fiscalYearFormSchema = z
  .object({
    name: z.string().trim().max(64, "Too long"),
    start_date: z.string().min(1, "Required"),
    end_date: z.string().min(1, "Required"),
  })
  .refine((value) => value.end_date > value.start_date, {
    message: "End date must be after the start date",
    path: ["end_date"],
  });
export type FiscalYearFormInput = z.input<typeof fiscalYearFormSchema>;
export type FiscalYearPayload = z.output<typeof fiscalYearFormSchema>;

/* ---- payment gateways ---- */
export const GATEWAY_PROVIDERS = ["razorpay", "stripe", "mock"] as const;
export type GatewayProvider = (typeof GATEWAY_PROVIDERS)[number];
export const GATEWAY_MODES = ["test", "live"] as const;
export type GatewayMode = (typeof GATEWAY_MODES)[number];
export const GATEWAY_METHODS = ["card", "upi"] as const;

/** One mode's key set — secrets are write-only (flags + last-4 hint only). */
export const modeKeysSchema = z.object({
  public_key: z.string().nullable(),
  has_secret: z.boolean(),
  secret_hint: z.string().nullable(),
  has_webhook_secret: z.boolean(),
  webhook_secret_hint: z.string().nullable(),
});
export type ModeKeys = z.infer<typeof modeKeysSchema>;

export const gatewaySchema = z.object({
  provider: z.string(),
  display_name: z.string(),
  is_enabled: z.boolean(),
  mode: z.enum(GATEWAY_MODES),
  supported_methods: z.array(z.string()),
  priority: z.number(),
  configured: z.boolean(),
  test: modeKeysSchema,
  live: modeKeysSchema,
  webhook_url: z.string(),
  updated_at: z.string().nullable(),
});
export type Gateway = z.infer<typeof gatewaySchema>;
export const gatewayListSchema = z.array(gatewaySchema);

/**
 * PUT payload. Secrets are omitted (keep), empty string (keep) or null
 * (clear); only an explicit replacement value is stored.
 */
export const gatewayUpdateSchema = z.object({
  is_enabled: z.boolean(),
  display_name: z.string().max(80).nullable(),
  mode: z.enum(GATEWAY_MODES),
  supported_methods: z.array(z.string()),
  priority: z.number().min(0).max(1000),
  test_public_key: z.string().nullable().optional(),
  test_secret: z.string().nullable().optional(),
  test_webhook_secret: z.string().nullable().optional(),
  live_public_key: z.string().nullable().optional(),
  live_secret: z.string().nullable().optional(),
  live_webhook_secret: z.string().nullable().optional(),
});
export type GatewayUpdatePayload = z.output<typeof gatewayUpdateSchema>;

export const gatewayTestResultSchema = z.object({
  ok: z.boolean(),
  message: z.string(),
  mode: z.string(),
});
export type GatewayTestResult = z.infer<typeof gatewayTestResultSchema>;
