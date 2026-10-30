import { z } from "zod";

export const INVOICE_STATUSES = ["draft", "posted", "cancelled"] as const;

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

/** Non-negative decimal kept as an exact string so no float rounding leaks into payloads. */
const decimalInput = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid number");

const positiveDecimalInput = decimalInput.refine((value) => Number(value) > 0, "Must be greater than 0");

export const invoiceSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  customer_id: z.string(),
  customer_name: z.string(),
  customer_address: z.string().nullable().default(null),
  customer_tax_identifier: z.string().nullable().default(null),
  status: z.string(),
  invoice_date: z.string(),
  due_date: z.string().nullable(),
  currency: z.string(),
  subtotal: decimalString,
  discount_total: decimalString,
  tax_total: decimalString,
  shipping_total: decimalString,
  total: decimalString,
  total_base: decimalString,
  order_id: z.string().nullable(),
  /** One entry per GST rate (detail responses; list responses may be empty). */
  tax_breakup: z
    .array(z.object({ rate: decimalString, taxable: decimalString, amount: decimalString }))
    .default([]),
});
export type Invoice = z.infer<typeof invoiceSchema>;

export const invoiceLineSchema = z.object({
  id: z.string(),
  product_id: z.string().nullable(),
  sku_snapshot: z.string(),
  /** HSN/SAC snapshot printed on the GST invoice. */
  hsn_sac: z.string().nullable().default(null),
  description_snapshot: z.string(),
  qty: decimalString,
  unit_price: decimalString,
  discount: decimalString,
  tax_percentage: decimalString,
  line_total: decimalString,
  tax_amount: decimalString,
});
export type InvoiceLine = z.infer<typeof invoiceLineSchema>;

export const creditNoteSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  invoice_id: z.string(),
  customer_id: z.string(),
  status: z.string(),
  note_date: z.string(),
  total: decimalString,
  reason: z.string().nullable(),
});
export type CreditNote = z.infer<typeof creditNoteSchema>;

export const agingBucketSchema = z.object({
  current: decimalString,
  d30: decimalString,
  d60: decimalString,
  d90: decimalString,
  older: decimalString,
});
export type AgingBucket = z.infer<typeof agingBucketSchema>;

/** AR aging is keyed by customer id (see `invoicing.service.ar_aging`). */
export const arAgingSchema = z.record(z.string(), agingBucketSchema);
export type ArAging = z.infer<typeof arAgingSchema>;

// ---- reference data (searchable pickers) ----

export const customerSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  email: z.string().nullable(),
});
export type Customer = z.infer<typeof customerSchema>;

export const taxRateSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  percentage: decimalString,
  is_active: z.boolean(),
});
export type TaxRate = z.infer<typeof taxRateSchema>;

export const storageLocationSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  location_type: z.string(),
  is_active: z.boolean(),
});
export type StorageLocation = z.infer<typeof storageLocationSchema>;

// ---- forms ----

export const invoiceLineFormSchema = z.object({
  product_id: z.string().nullable().optional(),
  description: z.string().trim().max(2000).optional(),
  qty: positiveDecimalInput,
  unit_price: decimalInput,
  discount: decimalInput,
  tax_rate_id: z.string().nullable().optional(),
  tax_percentage: decimalInput,
});
export type InvoiceLineFormInput = z.input<typeof invoiceLineFormSchema>;
export type InvoiceLinePayload = z.output<typeof invoiceLineFormSchema>;

export const invoiceFormSchema = z.object({
  customer_id: z.string().min(1, "Customer is required"),
  invoice_date: z.string().min(1, "Invoice date is required"),
  /** Optional buyer address snapshot, printed on the GST invoice. */
  customer_address: z.string().trim().max(500).optional(),
  currency: z.string().trim().length(3, "3-letter currency code"),
  shipping_total: decimalInput,
  /** Order-level manual discount, spread across the lines by value. */
  discount: decimalInput,
  due_date: z
    .string()
    .optional()
    .transform((value) => (value && value.length > 0 ? value : undefined)),
  notes: z.string().trim().max(4000).optional(),
  order_id: z.string().nullable().optional(),
  post: z.boolean(),
  lines: z.array(invoiceLineFormSchema).min(1, "Add at least one line"),
});
export type InvoiceFormInput = z.input<typeof invoiceFormSchema>;
export type InvoicePayload = z.output<typeof invoiceFormSchema>;

export const creditLineFormSchema = z.object({
  invoice_line_id: z.string().nullable().optional(),
  description: z.string().trim().max(2000).optional(),
  qty: positiveDecimalInput,
  unit_price: decimalInput,
  tax_amount: decimalInput,
});
export type CreditLineFormInput = z.input<typeof creditLineFormSchema>;

export const creditNoteFormSchema = z
  .object({
    invoice_id: z.string().min(1, "Invoice is required"),
    note_date: z.string().min(1, "Date is required"),
    reason: z.string().trim().max(2000).optional(),
    restock: z.boolean(),
    restock_location_id: z.string().nullable().optional(),
    lines: z.array(creditLineFormSchema).min(1, "Add at least one line"),
  })
  .refine((value) => !value.restock || Boolean(value.restock_location_id), {
    message: "A restock location is required when restocking",
    path: ["restock_location_id"],
  });
export type CreditNoteFormInput = z.input<typeof creditNoteFormSchema>;
export type CreditNotePayload = z.output<typeof creditNoteFormSchema>;

export const EMPTY_INVOICE_LINE: InvoiceLineFormInput = {
  product_id: null,
  description: "",
  qty: "1",
  unit_price: "0",
  discount: "0",
  tax_rate_id: null,
  tax_percentage: "0",
};
