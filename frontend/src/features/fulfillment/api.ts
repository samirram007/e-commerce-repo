import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  type Shipment,
  type ShipmentDetail,
  shipmentDetailSchema,
  shipmentSchema,
} from "./schemas";

export async function fetchShipments(
  filters: { status?: string; orderId?: string } = {},
): Promise<Shipment[]> {
  const { data } = await api.get("/shipments", {
    params: {
      status: filters.status || undefined,
      order_id: filters.orderId || undefined,
    },
  });
  return z.array(shipmentSchema).parse(data);
}

export async function fetchShipment(id: string): Promise<ShipmentDetail> {
  const { data } = await api.get(`/shipments/${id}`);
  return shipmentDetailSchema.parse(data);
}

export async function createShipment(orderId: string): Promise<Shipment> {
  const { data } = await api.post("/shipments", null, { params: { order_id: orderId } });
  return shipmentSchema.parse(data);
}

export async function transitionShipment(id: string, toStatus: string): Promise<Shipment> {
  const { data } = await api.post(`/shipments/${id}/transition`, null, {
    params: { to_status: toStatus },
  });
  return shipmentSchema.parse(data);
}

export async function dispatchShipment(id: string, carrier: string): Promise<Shipment> {
  const { data } = await api.post(`/shipments/${id}/dispatch`, null, {
    params: { carrier },
  });
  return shipmentSchema.parse(data);
}
