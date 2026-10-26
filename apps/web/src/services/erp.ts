import { api } from "../lib/api-client";

// ---- sales orders ----
export interface OrderBrief {
  id: string;
  doc_number: string;
  customer_id: string;
  status: string;
  payment_state: string;
  order_date: string;
  currency: string;
  total: string;
  invoice_id: string | null;
}

export async function listOrders(): Promise<OrderBrief[]> {
  const { data } = await api.get<OrderBrief[]>("/storefront/orders");
  return data;
}

export async function payOrder(orderId: string, idempotencyKey: string) {
  const { data } = await api.post(
    `/storefront/orders/${orderId}/pay`,
    { method: "mock_gateway", provider: "mock" },
    { headers: { "Idempotency-Key": idempotencyKey } },
  );
  return data as { order_id: string; status: string; invoice_id: string | null; payment_ref: string | null };
}

export async function cancelOrder(orderId: string) {
  const { data } = await api.post(`/storefront/orders/${orderId}/cancel`);
  return data as { id: string; status: string };
}

// ---- shipments (fulfillment) ----
export interface ShipmentBrief {
  id: string;
  doc_number: string;
  order_id: string;
  status: string;
  tracking_number: string | null;
}

export async function listShipments(): Promise<ShipmentBrief[]> {
  const { data } = await api.get<ShipmentBrief[]>("/shipments");
  return data;
}

export async function createShipment(orderId: string): Promise<ShipmentBrief> {
  const { data } = await api.post<ShipmentBrief>(`/shipments?order_id=${orderId}`);
  return data;
}

export async function transitionShipment(shipmentId: string, toStatus: string): Promise<ShipmentBrief> {
  const { data } = await api.post<ShipmentBrief>(
    `/shipments/${shipmentId}/transition?to_status=${toStatus}`,
  );
  return data;
}

export async function dispatchShipment(shipmentId: string): Promise<ShipmentBrief> {
  const { data } = await api.post<ShipmentBrief>(`/shipments/${shipmentId}/dispatch`);
  return data;
}

// ---- purchasing ----
export interface PurchaseOrderBrief {
  id: string;
  doc_number: string;
  vendor_id: string;
  status: string;
  order_date: string;
  total?: string;
}

export async function listPurchaseOrders(): Promise<PurchaseOrderBrief[]> {
  const { data } = await api.get<PurchaseOrderBrief[]>("/purchasing/orders");
  return data;
}

export async function poTransition(poId: string, toStatus: string): Promise<PurchaseOrderBrief> {
  const { data } = await api.post<PurchaseOrderBrief>(`/purchasing/orders/${poId}/${toStatus}`);
  return data;
}

export async function listVendorBills(): Promise<PurchaseOrderBrief[]> {
  const { data } = await api.get<PurchaseOrderBrief[]>("/purchasing/bills");
  return data;
}

// ---- inventory ----
export interface StockRow {
  product_id: string;
  location_id: string;
  batch_ref: string | null;
  on_hand: string;
  reserved: string;
  available: string;
}

export async function stockOnHand(): Promise<StockRow[]> {
  const { data } = await api.get<StockRow[]>("/inventory/on-hand");
  return data;
}

export interface LedgerRow {
  id: string;
  movement_type: string;
  sku: string;
  location_code: string;
  qty_delta: string;
  source_type: string;
  moved_at: string;
}

export async function stockLedger(): Promise<LedgerRow[]> {
  const { data } = await api.get<LedgerRow[]>("/inventory/ledger");
  return data;
}

export async function adjustStock(input: {
  location_id: string;
  product_id: string;
  quantity: string;
  direction: "increase" | "decrease";
  reason?: string;
}) {
  const { data } = await api.post("/inventory/adjustments", input);
  return data;
}

// ---- accounting ----
export interface JournalLineOut {
  id: string;
  account_code: string;
  account_name: string;
  side: string;
  amount: string;
  description: string | null;
}

export interface JournalEntryOut {
  id: string;
  doc_number: string;
  entry_date: string;
  description: string | null;
  status: string;
  source_type: string;
  reversal_of_id: string | null;
  lines: JournalLineOut[];
}

export async function listJournalEntries(): Promise<JournalEntryOut[]> {
  const { data } = await api.get<JournalEntryOut[]>("/accounting/journal-entries");
  return data;
}

export interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  account_type: string;
  debit: string;
  credit: string;
  balance: string;
}

export async function trialBalance(): Promise<TrialBalanceRow[]> {
  const { data } = await api.get<TrialBalanceRow[]>("/accounting/reports/trial-balance");
  return data;
}

export async function accounts(): Promise<{ id: string; code: string; name: string; account_type: string }[]> {
  const { data } = await api.get("/accounting/accounts");
  return data;
}

export async function postManualJournal(input: {
  entry_date: string;
  description?: string;
  lines: { account_code: string; side: "debit" | "credit"; amount: string; description?: string }[];
}) {
  const { data } = await api.post<JournalEntryOut>("/accounting/journal-entries", input);
  return data;
}

export async function reverseEntry(entryId: string) {
  const { data } = await api.post<JournalEntryOut>(`/accounting/journal-entries/${entryId}/reverse`);
  return data;
}

// ---- invoices ----
export interface InvoiceBrief {
  id: string;
  doc_number: string;
  customer_name: string;
  status: string;
  invoice_date: string;
  currency: string;
  total: string;
  total_base: string;
}

export async function listInvoices(): Promise<InvoiceBrief[]> {
  const { data } = await api.get<InvoiceBrief[]>("/invoices");
  return data;
}

// ---- reports ----
export async function salesSummary(fromDate?: string, toDate?: string) {
  const { data } = await api.get("/reports/sales-summary", { params: { from_date: fromDate, to_date: toDate } });
  return data as { invoice_count: number; total: string; tax_total: string };
}

export async function deliveryPerformance() {
  const { data } = await api.get("/reports/delivery-performance");
  return data as { statuses: Record<string, number>; on_time_rate: string; failure_count: number };
}

// ---- audit ----
export interface AuditRow {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_user_id: string | null;
  created_at: string;
}

export async function listAudit(): Promise<AuditRow[]> {
  const { data } = await api.get<AuditRow[]>("/audit");
  return data;
}
