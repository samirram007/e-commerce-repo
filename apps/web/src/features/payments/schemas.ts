import { z } from "zod";

export const PAYMENT_DIRECTIONS = ["receipt", "payment"] as const;
export const PAYMENT_METHODS = ["cash", "bank"] as const;

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

const decimalInput = z
  .string()
  .trim()
  .min(1, "Required")
  .regex(/^\d+(\.\d+)?$/, "Enter a valid number");

const positiveDecimalInput = decimalInput.refine((value) => Number(value) > 0, "Must be greater than 0");

export const paymentSchema = z.object({
  id: z.string(),
  direction: z.string(),
  provider: z.string(),
  provider_ref: z.string().nullable(),
  /** "test" | "live" credential mode of the charge; null for offline/manual. */
  mode: z.string().nullable().optional(),
  method: z.string(),
  status: z.string(),
  amount: decimalString,
  currency: z.string(),
  occurred_at: z.string(),
  order_id: z.string().nullable(),
});
export type Payment = z.infer<typeof paymentSchema>;

export const allocationSchema = z.object({
  id: z.string(),
  document_type: z.string().optional(),
  document_id: z.string(),
  amount: decimalString,
});
export type Allocation = z.infer<typeof allocationSchema>;

export const customerSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
});
export type Customer = z.infer<typeof customerSchema>;

export const vendorSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
});
export type Vendor = z.infer<typeof vendorSchema>;

export const paymentFormSchema = z
  .object({
    direction: z.enum(PAYMENT_DIRECTIONS),
    method: z.enum(PAYMENT_METHODS),
    party_id: z.string().min(1, "Select a party"),
    amount: positiveDecimalInput,
    occurred_at: z.string().min(1, "Date is required"),
    notes: z.string().trim().max(2000).optional(),
    allocate_invoice_id: z.string().nullable().optional(),
    allocation_amount: decimalInput,
  })
  .refine((value) => !value.allocate_invoice_id || Number(value.allocation_amount) > 0, {
    message: "Enter an allocation amount",
    path: ["allocation_amount"],
  });
export type PaymentFormInput = z.input<typeof paymentFormSchema>;

/** Body for `POST /payments` (see payments router `PaymentIn`). */
export interface PaymentCreateInput {
  direction: string;
  method: string;
  party_type: string;
  party_id: string;
  amount: string;
  occurred_at: string;
  notes?: string;
  allocations?: { document_type: string; document_id: string; amount: string }[];
}
