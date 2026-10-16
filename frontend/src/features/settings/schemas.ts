import { z } from "zod";

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
});
export type Company = z.infer<typeof companySchema>;

export const companyListSchema = z.array(companySchema);

export const companyCreateFormSchema = z.object({
  name: z.string().trim().min(2, "Use at least 2 characters").max(200, "Too long"),
  legal_name: z.string().trim().max(200, "Too long"),
  base_currency: z.string().trim().length(3, "Use a 3-letter code"),
  timezone: z.string().trim().min(1, "Required").max(64, "Too long"),
  locale: z.string().trim().min(1, "Required").max(16, "Too long"),
  address: z.string().trim().max(500, "Too long"),
  tax_identifier: z.string().trim().max(64, "Too long"),
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
export const LOCATION_TYPES = ["warehouse", "zone", "aisle", "rack", "bin"] as const;
export type LocationType = (typeof LOCATION_TYPES)[number];

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
