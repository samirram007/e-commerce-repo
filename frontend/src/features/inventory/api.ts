import { api } from "../../lib/api-client";
import {
  adjustmentResultSchema,
  countLineResultSchema,
  createCountResultSchema,
  locationOptionListSchema,
  ledgerListSchema,
  onHandListSchema,
  postCountResultSchema,
  productOptionListSchema,
  reconcileSchema,
  serialListSchema,
  stockCountSchema,
  transferResultSchema,
  valuationListSchema,
  type AdjustmentPayload,
  type CreateCountResult,
  type LedgerRow,
  type LocationOption,
  type OnHandRow,
  type PostCountResult,
  type ProductOption,
  type Reconcile,
  type SerialRow,
  type StockCount,
  type TransferPayload,
  type ValuationRow,
} from "./schemas";

export interface OnHandFilters {
  productId?: string;
  locationId?: string;
}

export async function fetchOnHand(filters: OnHandFilters = {}): Promise<OnHandRow[]> {
  const { data } = await api.get("/inventory/on-hand", {
    params: {
      product_id: filters.productId || undefined,
      location_id: filters.locationId || undefined,
    },
  });
  return onHandListSchema.parse(data);
}

export interface LedgerFilters {
  productId?: string;
  locationId?: string;
  limit?: number;
}

export async function fetchLedger(filters: LedgerFilters = {}): Promise<LedgerRow[]> {
  const { data } = await api.get("/inventory/ledger", {
    params: {
      product_id: filters.productId || undefined,
      location_id: filters.locationId || undefined,
      limit: filters.limit,
    },
  });
  return ledgerListSchema.parse(data);
}

export async function transferStock(input: TransferPayload): Promise<{ transfer_id: string }> {
  const { data } = await api.post("/inventory/transfers", input);
  return transferResultSchema.parse(data);
}

export async function adjustStock(
  input: AdjustmentPayload,
): Promise<{ ledger_entry_id: string; value: string; avg_cost: string }> {
  const { data } = await api.post("/inventory/adjustments", input);
  return adjustmentResultSchema.parse(data);
}

export async function createCount(locationId: string): Promise<CreateCountResult> {
  const { data } = await api.post("/inventory/counts", { location_id: locationId });
  return createCountResultSchema.parse(data);
}

export async function fetchCount(id: string): Promise<StockCount> {
  const { data } = await api.get(`/inventory/counts/${id}`);
  return stockCountSchema.parse(data);
}

export async function addCountLine(
  id: string,
  input: { product_id: string; counted_qty: string },
): Promise<{ id: string; variance: string }> {
  const { data } = await api.post(`/inventory/counts/${id}/lines`, input);
  return countLineResultSchema.parse(data);
}

export async function postCount(id: string): Promise<PostCountResult> {
  const { data } = await api.post(`/inventory/counts/${id}/post`);
  return postCountResultSchema.parse(data);
}

export async function fetchValuation(): Promise<ValuationRow[]> {
  const { data } = await api.get("/inventory/valuation");
  return valuationListSchema.parse(data);
}

export async function fetchReconcile(): Promise<Reconcile> {
  const { data } = await api.get("/inventory/reconcile");
  return reconcileSchema.parse(data);
}

export interface SerialFilters {
  productId?: string;
  locationId?: string;
  status?: string;
  search?: string;
}

export async function fetchSerials(filters: SerialFilters = {}): Promise<SerialRow[]> {
  const { data } = await api.get("/inventory/serials", {
    params: {
      product_id: filters.productId || undefined,
      location_id: filters.locationId || undefined,
      status: filters.status || undefined,
      search: filters.search || undefined,
    },
  });
  return serialListSchema.parse(data);
}

// ---- shared pickers ----
export async function fetchProductOptions(): Promise<ProductOption[]> {
  const { data } = await api.get("/catalog/products");
  return productOptionListSchema.parse(data).items;
}

export async function fetchLocationOptions(): Promise<LocationOption[]> {
  const { data } = await api.get("/storage/locations");
  return locationOptionListSchema.parse(data);
}
