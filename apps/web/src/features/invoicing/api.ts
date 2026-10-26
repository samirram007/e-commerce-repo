import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  arAgingSchema,
  creditNoteSchema,
  customerSchema,
  invoiceLineSchema,
  invoiceSchema,
  storageLocationSchema,
  taxRateSchema,
  type ArAging,
  type CreditNote,
  type CreditNotePayload,
  type Customer,
  type Invoice,
  type InvoiceLine,
  type InvoicePayload,
  type StorageLocation,
  type TaxRate,
} from "./schemas";

export interface InvoiceFilters {
  status?: string;
  customerId?: string;
}

export async function fetchInvoices(filters: InvoiceFilters = {}): Promise<Invoice[]> {
  const { data } = await api.get("/invoices", {
    params: { status: filters.status || undefined, customer_id: filters.customerId || undefined },
  });
  return z.array(invoiceSchema).parse(data);
}

export async function fetchInvoice(id: string): Promise<Invoice> {
  const { data } = await api.get(`/invoices/${id}`);
  return invoiceSchema.parse(data);
}

export async function fetchInvoiceLines(id: string): Promise<InvoiceLine[]> {
  const { data } = await api.get(`/invoices/${id}/lines`);
  return z.array(invoiceLineSchema).parse(data);
}

export async function createInvoice(payload: InvoicePayload): Promise<Invoice> {
  const { data } = await api.post("/invoices", payload);
  return invoiceSchema.parse(data);
}

export async function postInvoice(id: string): Promise<Invoice> {
  const { data } = await api.post(`/invoices/${id}/post`);
  return invoiceSchema.parse(data);
}

export async function reverseInvoice(id: string): Promise<Invoice> {
  const { data } = await api.post(`/invoices/${id}/reverse`);
  return invoiceSchema.parse(data);
}

export async function fetchCreditNotes(): Promise<CreditNote[]> {
  const { data } = await api.get("/invoices/credit-notes");
  return z.array(creditNoteSchema).parse(data);
}

export async function createCreditNote(payload: CreditNotePayload): Promise<CreditNote> {
  const { data } = await api.post("/invoices/credit-notes", payload);
  return creditNoteSchema.parse(data);
}

export async function fetchArAging(asOf: string): Promise<ArAging> {
  const { data } = await api.get("/invoices/reports/ar-aging", { params: { as_of: asOf } });
  return arAgingSchema.parse(data);
}

// ---- reference data used by the invoice / credit-note editors ----

export async function fetchCustomers(search?: string): Promise<Customer[]> {
  const { data } = await api.get("/partners/customers", {
    params: { search: search || undefined },
  });
  return z.array(customerSchema).parse(data);
}

export async function fetchTaxRates(): Promise<TaxRate[]> {
  const { data } = await api.get("/taxes");
  return z.array(taxRateSchema).parse(data);
}

export async function fetchLocations(): Promise<StorageLocation[]> {
  const { data } = await api.get("/storage/locations");
  return z.array(storageLocationSchema).parse(data);
}
