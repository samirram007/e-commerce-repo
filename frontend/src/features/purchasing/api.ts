import { api } from "../../lib/api-client";
import {
  goodsReceiptSchema,
  locationOptionListSchema,
  productOptionListSchema,
  purchaseOrderLineListSchema,
  purchaseOrderListSchema,
  purchaseOrderSchema,
  vendorBillLineListSchema,
  vendorBillListSchema,
  vendorBillSchema,
  vendorOptionListSchema,
  type AdhocBillPayload,
  type BillFromReceiptFormInput,
  type GoodsReceipt,
  type LocationOption,
  type ProductOption,
  type PurchaseOrder,
  type PurchaseOrderLine,
  type PurchaseOrderPayload,
  type ReceiveLinePayload,
  type VendorBill,
  type VendorBillLine,
  type VendorOption,
} from "./schemas";

export async function fetchPurchaseOrders(status?: string): Promise<PurchaseOrder[]> {
  const { data } = await api.get("/purchasing/orders", {
    params: { status: status || undefined },
  });
  return purchaseOrderListSchema.parse(data);
}

export async function fetchPurchaseOrder(id: string): Promise<PurchaseOrder> {
  const { data } = await api.get(`/purchasing/orders/${id}`);
  return purchaseOrderSchema.parse(data);
}

export async function fetchPurchaseOrderLines(id: string): Promise<PurchaseOrderLine[]> {
  const { data } = await api.get(`/purchasing/orders/${id}/lines`);
  return purchaseOrderLineListSchema.parse(data);
}

export async function createPurchaseOrder(input: PurchaseOrderPayload): Promise<PurchaseOrder> {
  const { data } = await api.post("/purchasing/orders", input);
  return purchaseOrderSchema.parse(data);
}

export type PoAction = "submit" | "approve" | "cancel";

export async function transitionPurchaseOrder(id: string, action: PoAction): Promise<PurchaseOrder> {
  const { data } = await api.post(`/purchasing/orders/${id}/${action}`);
  return purchaseOrderSchema.parse(data);
}

export async function receiveGoods(
  id: string,
  lines: ReceiveLinePayload[],
): Promise<GoodsReceipt> {
  const { data } = await api.post(`/purchasing/orders/${id}/receive`, { lines });
  return goodsReceiptSchema.parse(data);
}

export async function createBillFromReceipt(
  input: BillFromReceiptFormInput,
): Promise<VendorBill> {
  const { data } = await api.post(
    `/purchasing/bills/from-receipt/${input.receipt_id}`,
    null,
    { params: { bill_date: input.bill_date, vendor_ref: input.vendor_ref || undefined } },
  );
  return vendorBillSchema.parse(data);
}

export async function createAdhocBill(input: AdhocBillPayload): Promise<VendorBill> {
  const { data } = await api.post("/purchasing/bills", input);
  return vendorBillSchema.parse(data);
}

export async function fetchVendorBills(): Promise<VendorBill[]> {
  const { data } = await api.get("/purchasing/bills");
  return vendorBillListSchema.parse(data);
}

export async function fetchVendorBillLines(id: string): Promise<VendorBillLine[]> {
  const { data } = await api.get(`/purchasing/bills/${id}/lines`);
  return vendorBillLineListSchema.parse(data);
}

// ---- shared pickers ----
export async function fetchVendors(): Promise<VendorOption[]> {
  const { data } = await api.get("/partners/vendors");
  return vendorOptionListSchema.parse(data);
}

export async function fetchProductOptions(): Promise<ProductOption[]> {
  const { data } = await api.get("/catalog/products");
  return productOptionListSchema.parse(data).items;
}

export async function fetchLocationOptions(): Promise<LocationOption[]> {
  const { data } = await api.get("/storage/locations");
  return locationOptionListSchema.parse(data);
}
