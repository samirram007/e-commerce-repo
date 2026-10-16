import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCreditNote,
  createInvoice,
  fetchArAging,
  fetchCreditNotes,
  fetchCustomers,
  fetchInvoice,
  fetchInvoiceLines,
  fetchInvoices,
  fetchLocations,
  fetchTaxRates,
  postInvoice,
  reverseInvoice,
  type InvoiceFilters,
} from "./api";
import type { CreditNotePayload, InvoicePayload } from "./schemas";

export const invoicingKeys = {
  all: ["invoicing"] as const,
  invoices: (filters: InvoiceFilters) => [...invoicingKeys.all, "invoices", filters] as const,
  invoice: (id: string) => [...invoicingKeys.all, "invoice", id] as const,
  invoiceLines: (id: string) => [...invoicingKeys.all, "invoice", id, "lines"] as const,
  creditNotes: () => [...invoicingKeys.all, "credit-notes"] as const,
  arAging: (asOf: string) => [...invoicingKeys.all, "ar-aging", asOf] as const,
  customers: () => [...invoicingKeys.all, "customers"] as const,
  taxRates: () => [...invoicingKeys.all, "tax-rates"] as const,
  locations: () => [...invoicingKeys.all, "locations"] as const,
};

export function invoicesQueryOptions(filters: InvoiceFilters = {}) {
  return queryOptions({
    queryKey: invoicingKeys.invoices(filters),
    queryFn: () => fetchInvoices(filters),
  });
}

export function invoiceQueryOptions(id: string) {
  return queryOptions({
    queryKey: invoicingKeys.invoice(id),
    queryFn: () => fetchInvoice(id),
    enabled: Boolean(id),
  });
}

export function invoiceLinesQueryOptions(id: string) {
  return queryOptions({
    queryKey: invoicingKeys.invoiceLines(id),
    queryFn: () => fetchInvoiceLines(id),
    enabled: Boolean(id),
  });
}

export function creditNotesQueryOptions() {
  return queryOptions({
    queryKey: invoicingKeys.creditNotes(),
    queryFn: fetchCreditNotes,
  });
}

export function arAgingQueryOptions(asOf: string) {
  return queryOptions({
    queryKey: invoicingKeys.arAging(asOf),
    queryFn: () => fetchArAging(asOf),
    enabled: Boolean(asOf),
  });
}

export function customersQueryOptions() {
  return queryOptions({
    queryKey: invoicingKeys.customers(),
    queryFn: () => fetchCustomers(),
    staleTime: 5 * 60_000,
  });
}

export function taxRatesQueryOptions() {
  return queryOptions({
    queryKey: invoicingKeys.taxRates(),
    queryFn: fetchTaxRates,
    staleTime: 5 * 60_000,
  });
}

export function locationsQueryOptions() {
  return queryOptions({
    queryKey: invoicingKeys.locations(),
    queryFn: fetchLocations,
    staleTime: 5 * 60_000,
  });
}

function useInvalidateInvoicing() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: invoicingKeys.all });
}

export function useCreateInvoice() {
  const invalidate = useInvalidateInvoicing();
  return useMutation({
    mutationFn: (input: InvoicePayload) => createInvoice(input),
    onSuccess: invalidate,
  });
}

export function usePostInvoice() {
  const invalidate = useInvalidateInvoicing();
  return useMutation({
    mutationFn: (id: string) => postInvoice(id),
    onSuccess: invalidate,
  });
}

export function useReverseInvoice() {
  const invalidate = useInvalidateInvoicing();
  return useMutation({
    mutationFn: (id: string) => reverseInvoice(id),
    onSuccess: invalidate,
  });
}

export function useCreateCreditNote() {
  const invalidate = useInvalidateInvoicing();
  return useMutation({
    mutationFn: (input: CreditNotePayload) => createCreditNote(input),
    onSuccess: invalidate,
  });
}
