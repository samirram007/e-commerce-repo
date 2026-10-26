import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const PO_STATUSES = [
  "draft",
  "submitted",
  "approved",
  "partially_received",
  "received",
  "closed",
  "cancelled",
] as const;
export type PoStatus = (typeof PO_STATUSES)[number];

export const CURRENCIES = ["INR", "USD", "EUR", "GBP", "ZAR", "AUD", "CAD", "JPY"] as const;

// ---- response schemas (backend shapes) ----
export const purchaseOrderSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  vendor_id: z.string(),
  status: z.string(),
  order_date: z.string(),
  expected_date: z.string().nullable(),
  currency: z.string(),
  received_qty: decimalString,
  approved_by: z.string().nullable(),
});
export type PurchaseOrder = z.infer<typeof purchaseOrderSchema>;
export const purchaseOrderListSchema = z.array(purchaseOrderSchema);

export const purchaseOrderLineSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  ordered_qty: decimalString,
  received_qty: decimalString,
  unit_cost: decimalString,
  tax_rate_id: z.string().nullable(),
});
export type PurchaseOrderLine = z.infer<typeof purchaseOrderLineSchema>;
export const purchaseOrderLineListSchema = z.array(purchaseOrderLineSchema);

export const goodsReceiptLineSchema = z.object({
  id: z.string(),
  order_line_id: z.string(),
  product_id: z.string(),
  qty_received: decimalString,
  unit_cost: decimalString,
});
export const goodsReceiptSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  order_id: z.string(),
  status: z.string(),
  received_at: z.string(),
  lines: z.array(goodsReceiptLineSchema),
});
export type GoodsReceipt = z.infer<typeof goodsReceiptSchema>;

export const vendorBillSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  vendor_id: z.string(),
  status: z.string(),
  bill_date: z.string(),
  due_date: z.string().nullable(),
  currency: z.string(),
  total: decimalString,
  total_base: decimalString,
});
export type VendorBill = z.infer<typeof vendorBillSchema>;
export const vendorBillListSchema = z.array(vendorBillSchema);

export const vendorBillLineSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  qty: decimalString,
  unit_cost: decimalString,
  line_total: decimalString,
  tax_amount: decimalString,
});
export type VendorBillLine = z.infer<typeof vendorBillLineSchema>;
export const vendorBillLineListSchema = z.array(vendorBillLineSchema);

// ---- shared picker schemas (reuse endpoints from other modules) ----
export const vendorOptionSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
});
export type VendorOption = z.infer<typeof vendorOptionSchema>;
export const vendorOptionListSchema = z.array(vendorOptionSchema);

export const productOptionSchema = z.object({
  id: z.string(),
  sku: z.string(),
  name: z.string(),
  uom_id: z.string().nullable().optional(),
  default_tax_rate_id: z.string().nullable().optional(),
  base_cost: decimalString,
  is_purchasable: z.boolean().optional(),
  track_batches: z.boolean().optional(),
  track_serials: z.boolean().optional(),
});
export type ProductOption = z.infer<typeof productOptionSchema>;
export const productOptionListSchema = z.object({
  items: z.array(productOptionSchema),
  total: z.number().optional(),
});

export const locationOptionSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  location_type: z.string(),
  parent_id: z.string().nullable(),
  is_active: z.boolean(),
});
export type LocationOption = z.infer<typeof locationOptionSchema>;
export const locationOptionListSchema = z.array(locationOptionSchema);

// ---- form validation ----
const positiveQty = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid quantity")
  .refine((value) => Number(value) > 0, "Must be greater than 0");

const nonNegativeAmount = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid amount");

const requiredDate = z
  .string()
  .trim()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD");

const optionalDate = z
  .string()
  .trim()
  .refine((value) => value === "" || /^\d{4}-\d{2}-\d{2}$/.test(value), "Use YYYY-MM-DD");

const currencyCode = z
  .string()
  .trim()
  .regex(/^[A-Za-z]{3}$/, "3-letter currency code");

export const poLineFormSchema = z.object({
  product_id: z.string().min(1, "Select a product"),
  ordered_qty: positiveQty,
  unit_cost: nonNegativeAmount,
  uom_id: z.string().nullable(),
  tax_rate_id: z.string().nullable(),
  notes: z.string().optional(),
});
export type PoLineForm = z.infer<typeof poLineFormSchema>;

export const poFormSchema = z.object({
  vendor_id: z.string().min(1, "Select a vendor"),
  order_date: requiredDate,
  expected_date: optionalDate,
  currency: currencyCode,
  notes: z.string().optional(),
  lines: z.array(poLineFormSchema).min(1, "Add at least one line"),
});
export type PoFormInput = z.input<typeof poFormSchema>;

export interface PurchaseOrderLinePayload {
  product_id: string;
  ordered_qty: string;
  unit_cost: string;
  uom_id: string | null;
  tax_rate_id: string | null;
  notes?: string;
}

export interface PurchaseOrderPayload {
  vendor_id: string;
  order_date: string;
  expected_date: string | null;
  currency: string;
  notes?: string;
  lines: PurchaseOrderLinePayload[];
}

export const receiveFormSchema = z.object({
  location_id: z.string().min(1, "Select a location"),
  lines: z
    .array(
      z.object({
        order_line_id: z.string(),
        qty_received: positiveQty,
        batch_ref: z.string().optional(),
        serials: z.string().optional(),
      }),
    )
    .min(1, "Enter at least one quantity"),
});
export type ReceiveFormInput = z.input<typeof receiveFormSchema>;

export interface ReceiveLinePayload {
  order_line_id: string;
  qty_received: string;
  location_id: string;
  batch_ref?: string;
  serials?: string[];
}

export const billLineFormSchema = z.object({
  product_id: z.string().nullable(),
  description: z.string().optional(),
  qty: positiveQty,
  unit_cost: nonNegativeAmount,
  tax_percentage: nonNegativeAmount.optional(),
});
export type BillLineForm = z.infer<typeof billLineFormSchema>;

export const adhocBillFormSchema = z.object({
  vendor_id: z.string().min(1, "Select a vendor"),
  bill_date: requiredDate,
  currency: currencyCode,
  lines: z.array(billLineFormSchema).min(1, "Add at least one line"),
});
export type AdhocBillFormInput = z.input<typeof adhocBillFormSchema>;

export interface AdhocBillLinePayload {
  product_id?: string | null;
  description?: string;
  qty: string;
  unit_cost: string;
  tax_percentage: string;
}

export interface AdhocBillPayload {
  vendor_id: string;
  bill_date: string;
  currency: string;
  lines: AdhocBillLinePayload[];
}

export const billFromReceiptFormSchema = z.object({
  receipt_id: z.string().trim().min(1, "Enter a receipt id"),
  bill_date: requiredDate,
  vendor_ref: z.string().optional(),
});
export type BillFromReceiptFormInput = z.input<typeof billFromReceiptFormSchema>;
