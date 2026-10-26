import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const PARTNER_TYPES = ["customer", "vendor"] as const;
export type PartnerType = (typeof PARTNER_TYPES)[number];

export const ADDRESS_TYPES = ["billing", "shipping"] as const;
export type AddressType = (typeof ADDRESS_TYPES)[number];

export const customerSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  payment_term_days: z.number(),
  credit_limit: decimalString,
  is_active: z.boolean(),
  notes: z.string().nullable(),
});
export type Customer = z.infer<typeof customerSchema>;

export const vendorSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  payment_term_days: z.number(),
  is_active: z.boolean(),
  notes: z.string().nullable(),
});
export type Vendor = z.infer<typeof vendorSchema>;

/** Either partner shape, discriminated by the tab/type at the call site. */
export type Partner = Customer | Vendor;

export const addressSchema = z.object({
  id: z.string(),
  partner_type: z.string(),
  partner_id: z.string(),
  address_type: z.string(),
  line1: z.string(),
  line2: z.string().nullable(),
  city: z.string().nullable(),
  region: z.string().nullable(),
  postal_code: z.string().nullable(),
  country: z.string().nullable(),
  is_default: z.boolean(),
});
export type Address = z.infer<typeof addressSchema>;

const intInput = z
  .string()
  .trim()
  .regex(/^\d+$/, "Enter a whole number")
  .transform((value) => Number(value));

const moneyInput = z
  .string()
  .trim()
  .regex(/^\d+(\.\d+)?$/, "Enter a valid amount")
  .transform((value) => Number(value));

const optionalText = (max: number) => z.string().trim().max(max).optional();

export const partnerFormSchema = z.object({
  partner_type: z.enum(PARTNER_TYPES),
  code: z.string().trim().min(1, "Code is required").max(32),
  name: z.string().trim().min(1, "Name is required").max(200),
  email: optionalText(255),
  phone: optionalText(50),
  tax_identifier: optionalText(64),
  payment_term_days: intInput,
  credit_limit: moneyInput,
  is_active: z.boolean(),
  notes: optionalText(2000),
});
export type PartnerFormInput = z.input<typeof partnerFormSchema>;
export type PartnerPayload = z.output<typeof partnerFormSchema>;
/** Create payload: `partner_type` selects the collection, it is not a backend field. */
export type PartnerCreatePayload = Omit<PartnerPayload, "partner_type">;

export const partnerUpdateSchema = partnerFormSchema.omit({ partner_type: true, code: true });
export type PartnerUpdatePayload = z.output<typeof partnerUpdateSchema>;

export const addressFormSchema = z.object({
  address_type: z.enum(ADDRESS_TYPES),
  line1: z.string().trim().min(1, "Address line is required").max(200),
  line2: optionalText(200),
  city: optionalText(100),
  region: optionalText(100),
  postal_code: optionalText(20),
  country: optionalText(2),
  is_default: z.boolean(),
});
export type AddressFormInput = z.input<typeof addressFormSchema>;
export type AddressPayload = z.output<typeof addressFormSchema>;
