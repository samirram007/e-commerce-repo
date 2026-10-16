import { z } from "zod";

/** Quantities arrive from the API as decimal strings (Pydantic v2 JSON). */
const decimalString = z.union([z.string(), z.number()]).transform((value) => String(value));

export const SHIPMENT_STATUSES = [
  "created",
  "picking",
  "picked",
  "packed",
  "dispatched",
  "in_transit",
  "delivered",
  "failed",
  "returned_to_origin",
  "cancelled_shipment",
] as const;
export type ShipmentStatus = (typeof SHIPMENT_STATUSES)[number];

/** Mirrors the backend LEGAL_TRANSITIONS state machine. */
export const SHIPMENT_TRANSITIONS: Record<string, string[]> = {
  created: ["picking", "cancelled_shipment"],
  picking: ["picked"],
  picked: ["packed"],
  packed: ["dispatched"],
  dispatched: ["in_transit"],
  in_transit: ["delivered", "failed"],
  failed: ["returned_to_origin", "in_transit"],
  returned_to_origin: ["delivered"],
  delivered: [],
};

export const shipmentSchema = z.object({
  id: z.string(),
  doc_number: z.string(),
  order_id: z.string(),
  status: z.string(),
  carrier: z.string().nullable(),
  tracking_number: z.string().nullable(),
  dispatched_at: z.string().nullable(),
  delivered_at: z.string().nullable(),
  shipping_address: z.string().nullable(),
});
export type Shipment = z.infer<typeof shipmentSchema>;

export const shipmentLineSchema = z.object({
  id: z.string(),
  order_line_id: z.string(),
  product_id: z.string(),
  from_location_id: z.string(),
  qty: decimalString,
});
export type ShipmentLine = z.infer<typeof shipmentLineSchema>;

export const shipmentDetailSchema = shipmentSchema.extend({
  lines: z.array(shipmentLineSchema),
});
export type ShipmentDetail = z.infer<typeof shipmentDetailSchema>;

export const createShipmentFormSchema = z.object({
  order_id: z.string().min(1, "Select an order"),
});
export type CreateShipmentFormInput = z.input<typeof createShipmentFormSchema>;
export type CreateShipmentPayload = z.output<typeof createShipmentFormSchema>;

export const dispatchFormSchema = z.object({
  carrier: z.string().trim().min(1, "Carrier is required"),
});
export type DispatchFormInput = z.input<typeof dispatchFormSchema>;
export type DispatchPayload = z.output<typeof dispatchFormSchema>;
