import { z } from "zod";

/** Money/quantity values arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const ORDER_STATUSES = [
  "pending_payment",
  "paid",
  "confirmed",
  "fulfilling",
  "shipped",
  "delivered",
  "cancelled",
  "refunded",
] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const orderSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  customer_id: z.string(),
  status: z.string(),
  payment_state: z.string(),
  order_date: z.string(),
  currency: z.string(),
  subtotal: decimalString,
  tax_total: decimalString,
  shipping_total: decimalString,
  total: decimalString,
  invoice_id: z.string().nullable(),
  shipping_address: z.string().nullable(),
});
export type Order = z.infer<typeof orderSchema>;

export const orderLineSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  sku: z.string(),
  qty: decimalString,
  unit_price: decimalString,
  line_total: decimalString,
  tax_amount: decimalString,
});
export type OrderLine = z.infer<typeof orderLineSchema>;

export const orderDetailSchema = orderSchema.extend({ lines: z.array(orderLineSchema) });
export type OrderDetail = z.infer<typeof orderDetailSchema>;

export const cartItemSchema = z.object({
  id: z.string(),
  product_id: z.string(),
  qty: decimalString,
});
export type CartItem = z.infer<typeof cartItemSchema>;

export const quoteLineSchema = z.object({
  item_id: z.string(),
  product_id: z.string(),
  sku: z.string(),
  qty: decimalString,
  unit_price: decimalString,
  tax_amount: decimalString,
  line_total: decimalString,
});
export type QuoteLine = z.infer<typeof quoteLineSchema>;

export const cartQuoteSchema = z.object({
  cart_id: z.string(),
  lines: z.array(quoteLineSchema),
  subtotal: decimalString,
  discount_total: decimalString,
  tax_total: decimalString,
  shipping_total: decimalString,
  total: decimalString,
  currency: z.string(),
});
export type CartQuote = z.infer<typeof cartQuoteSchema>;

export const cartSchema = z.object({
  id: z.string(),
  status: z.string(),
  items: z.array(cartItemSchema),
  quote: cartQuoteSchema,
});
export type Cart = z.infer<typeof cartSchema>;

export const checkoutResultSchema = z.object({
  order_id: z.string(),
  doc_number: z.string(),
  status: z.string(),
  total: decimalString,
  replayed: z.boolean(),
});
export type CheckoutResult = z.infer<typeof checkoutResultSchema>;

export const payResultSchema = z.object({
  order_id: z.string(),
  status: z.string(),
  payment_state: z.string(),
  invoice_id: z.string().nullable(),
  payment_ref: z.string().nullable(),
});
export type PayResult = z.infer<typeof payResultSchema>;

const amountInput = z
  .string()
  .trim()
  .regex(/^\d+(\.\d+)?$/, "Enter a valid amount");

export const cartItemFormSchema = z.object({
  product_id: z.string().min(1, "Select a product"),
  qty: amountInput,
});
export type CartItemFormInput = z.input<typeof cartItemFormSchema>;

export const checkoutFormSchema = z.object({
  customer_id: z.string().min(1, "Select a customer"),
  shipping_address: z.string().trim().max(500).optional(),
  billing_address: z.string().trim().max(500).optional(),
  shipping_total: amountInput,
  notes: z.string().trim().max(2000).optional(),
});
export type CheckoutFormInput = z.input<typeof checkoutFormSchema>;
export type CheckoutPayload = z.output<typeof checkoutFormSchema>;

export const payFormSchema = z.object({
  method: z.string().trim().min(1, "Method is required"),
  provider: z.string().trim().min(1, "Provider is required"),
});
export type PayFormInput = z.input<typeof payFormSchema>;
export type PayPayload = z.output<typeof payFormSchema>;
