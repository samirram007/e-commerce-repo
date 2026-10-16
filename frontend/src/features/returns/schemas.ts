import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const RETURN_STATUSES = [
  "requested",
  "approved",
  "rejected",
  "completed",
  "cancelled",
] as const;
export type ReturnStatus = (typeof RETURN_STATUSES)[number];

export const DISPOSITIONS = ["resalable", "damaged", "quarantined", "discarded"] as const;
export type Disposition = (typeof DISPOSITIONS)[number];

export const salesReturnSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  order_id: z.string(),
  invoice_id: z.string().nullable(),
  customer_id: z.string(),
  status: z.string(),
  credit_note_id: z.string().nullable(),
  refund_payment_id: z.string().nullable(),
});
export type SalesReturn = z.infer<typeof salesReturnSchema>;

export const returnLineSchema = z.object({
  id: z.string(),
  order_line_id: z.string(),
  product_id: z.string(),
  qty: decimalString,
  unit_price: decimalString,
  disposition: z.string(),
});
export type ReturnLine = z.infer<typeof returnLineSchema>;

export const returnDetailSchema = salesReturnSchema.extend({
  lines: z.array(returnLineSchema),
});
export type ReturnDetail = z.infer<typeof returnDetailSchema>;

const qtyInput = z
  .string()
  .trim()
  .regex(/^\d+(\.\d+)?$/, "Enter a valid quantity");

/** A line the user is composing before it is added to the return. */
export const returnLineDraftSchema = z.object({
  order_line_id: z.string().min(1, "Select a product line"),
  qty: qtyInput,
  disposition: z.enum(DISPOSITIONS),
});
export type ReturnLineDraftInput = z.input<typeof returnLineDraftSchema>;
export type ReturnLineDraft = z.output<typeof returnLineDraftSchema>;

export const returnCreateFormSchema = z.object({
  order_id: z.string().min(1, "Select an order"),
  notes: z.string().trim().max(2000).optional(),
});
export type ReturnCreateFormInput = z.input<typeof returnCreateFormSchema>;

/** Shape sent to POST /returns. */
export interface ReturnCreatePayload {
  order_id: string;
  notes?: string;
  lines: {
    order_line_id: string;
    qty: number;
    disposition: Disposition;
    restock_location_id?: string | null;
  }[];
}
