import { z } from "zod";

export const STOCK_TYPES = ["stock", "service", "non_inventory"] as const;

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const productSchema = z.object({
  id: z.string(),
  sku: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  category_id: z.string().nullable(),
  uom_id: z.string().nullable(),
  barcode: z.string().nullable(),
  /** HSN (goods) / SAC (services) code printed on GST invoices. */
  hsn_sac: z.string().nullable(),
  stock_type: z.string(),
  track_batches: z.boolean(),
  track_serials: z.boolean(),
  base_cost: decimalString,
  base_price: decimalString,
  /** Shipping measures: carriers rate a parcel by weight and size. */
  weight_kg: decimalString.nullable(),
  length_cm: decimalString.nullable(),
  width_cm: decimalString.nullable(),
  height_cm: decimalString.nullable(),
  default_tax_rate_id: z.string().nullable(),
  image_file_id: z.string().nullable(),
  is_active: z.boolean(),
  is_sellable: z.boolean(),
  is_purchasable: z.boolean(),
});
export type Product = z.infer<typeof productSchema>;

export const productListSchema = z.object({
  items: z.array(productSchema),
  total: z.number(),
});
export type ProductList = z.infer<typeof productListSchema>;

export const categorySchema = z.object({
  id: z.string(),
  name: z.string(),
  parent_id: z.string().nullable(),
});
export type Category = z.infer<typeof categorySchema>;

export const uomSchema = z.object({ id: z.string(), code: z.string(), name: z.string() });
export type Uom = z.infer<typeof uomSchema>;

const moneyInput = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid amount")
  .transform((value) => Number(value));

/** Optional measurement (kg / cm): blank means "not specified" and is sent as null. */
const measureInput = z
  .string()
  .trim()
  .regex(/^\d*(\.\d{1,3})?$/, "Enter a number")
  .transform((value) => (value === "" ? null : value));

export const productFormSchema = z.object({
  sku: z.string().trim().min(1, "SKU is required").max(64),
  name: z.string().trim().min(1, "Name is required").max(200),
  description: z.string().trim().max(2000).optional(),
  category_id: z.string().nullable().optional(),
  uom_id: z.string().nullable().optional(),
  barcode: z.string().trim().max(64).optional(),
  hsn_sac: z
    .string()
    .trim()
    .max(12)
    .refine((value) => value === "" || /^\d{4,8}$/.test(value), "Use a 4–8 digit HSN/SAC code")
    .optional(),
  stock_type: z.enum(STOCK_TYPES),
  track_batches: z.boolean(),
  track_serials: z.boolean(),
  base_cost: moneyInput,
  base_price: moneyInput,
  weight_kg: measureInput,
  length_cm: measureInput,
  width_cm: measureInput,
  height_cm: measureInput,
  is_sellable: z.boolean(),
  is_purchasable: z.boolean(),
  is_active: z.boolean(),
});
export type ProductFormInput = z.input<typeof productFormSchema>;
export type ProductPayload = z.output<typeof productFormSchema>;

export const categoryFormSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  parent_id: z.string().nullable().optional(),
});

export const uomFormSchema = z.object({
  code: z.string().trim().min(1, "Code is required").max(16),
  name: z.string().trim().min(1, "Name is required").max(50),
});
