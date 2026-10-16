import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const ADJUSTMENT_DIRECTIONS = ["increase", "decrease"] as const;
export type AdjustmentDirection = (typeof ADJUSTMENT_DIRECTIONS)[number];

// ---- response schemas ----
export const onHandRowSchema = z.object({
  product_id: z.string(),
  location_id: z.string(),
  batch_ref: z.string().nullable(),
  on_hand: decimalString,
  reserved: decimalString,
  available: decimalString,
});
export type OnHandRow = z.infer<typeof onHandRowSchema>;
export const onHandListSchema = z.array(onHandRowSchema);

export const ledgerRowSchema = z.object({
  id: z.string(),
  movement_type: z.string(),
  sku: z.string(),
  location_code: z.string(),
  qty_delta: decimalString,
  unit_cost: z.union([z.string(), z.number(), z.null()]).transform((value) =>
    value === null ? null : String(value),
  ),
  batch_ref: z.string().nullable(),
  source_type: z.string(),
  source_id: z.string(),
  moved_at: z.string(),
});
export type LedgerRow = z.infer<typeof ledgerRowSchema>;
export const ledgerListSchema = z.array(ledgerRowSchema);

export const valuationRowSchema = z.object({
  product_id: z.string(),
  sku: z.string(),
  avg_cost: decimalString,
  total_qty: decimalString,
  total_value: decimalString,
});
export type ValuationRow = z.infer<typeof valuationRowSchema>;
export const valuationListSchema = z.array(valuationRowSchema);

export const reconcileSchema = z.object({ balanced: z.boolean() });
export type Reconcile = z.infer<typeof reconcileSchema>;

export const countLineSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  counted_qty: decimalString,
  system_qty: decimalString,
  variance: decimalString,
});
export type CountLine = z.infer<typeof countLineSchema>;

export const stockCountSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  location_id: z.string(),
  status: z.string(),
  lines: z.array(countLineSchema),
});
export type StockCount = z.infer<typeof stockCountSchema>;

export const transferResultSchema = z.object({ transfer_id: z.string() });
export const adjustmentResultSchema = z.object({
  ledger_entry_id: z.string(),
  value: decimalString,
  avg_cost: decimalString,
});

export const createCountResultSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  status: z.string(),
});
export type CreateCountResult = z.infer<typeof createCountResultSchema>;

export const countLineResultSchema = z.object({
  id: z.string(),
  variance: decimalString,
});

export const postCountResultSchema = z.object({
  id: z.string(),
  status: z.string(),
  variance_value: decimalString,
});
export type PostCountResult = z.infer<typeof postCountResultSchema>;

// ---- shared picker schemas ----
export const productOptionSchema = z.object({
  id: z.string(),
  sku: z.string(),
  name: z.string(),
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

const nonNegativeQty = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid quantity");

export const transferFormSchema = z
  .object({
    product_id: z.string().min(1, "Select a product"),
    from_location_id: z.string().min(1, "Select a source"),
    to_location_id: z.string().min(1, "Select a destination"),
    quantity: positiveQty,
  })
  .refine((value) => value.from_location_id !== value.to_location_id, {
    message: "Source and destination must differ",
    path: ["to_location_id"],
  });
export type TransferFormInput = z.input<typeof transferFormSchema>;

export interface TransferPayload {
  product_id: string;
  from_location_id: string;
  to_location_id: string;
  quantity: string;
}

export const adjustmentFormSchema = z.object({
  product_id: z.string().min(1, "Select a product"),
  location_id: z.string().min(1, "Select a location"),
  quantity: positiveQty,
  direction: z.enum(ADJUSTMENT_DIRECTIONS),
  reason: z.string().optional(),
});
export type AdjustmentFormInput = z.input<typeof adjustmentFormSchema>;

export interface AdjustmentPayload {
  product_id: string;
  location_id: string;
  quantity: string;
  direction: AdjustmentDirection;
  reason?: string;
}

export const createCountFormSchema = z.object({
  location_id: z.string().min(1, "Select a location"),
});
export type CreateCountFormInput = z.input<typeof createCountFormSchema>;

export const countLineFormSchema = z.object({
  product_id: z.string().min(1, "Select a product"),
  counted_qty: nonNegativeQty,
});
export type CountLineFormInput = z.input<typeof countLineFormSchema>;
