import { z } from "zod";
import { api } from "../../lib/api-client";
import {
  closeFiscalYearResultSchema,
  companyListSchema,
  companySchema,
  companyAddressOutSchema,
  CompanyAddressOut,
  fiscalYearListSchema,
  fiscalYearPeriodListSchema,
  fiscalYearSchema,
  forwardFiscalYearResultSchema,
  openingBalancesResultSchema,
  storageLocationListSchema,
  storageLocationSchema,
  taxRateListSchema,
  taxRateSchema,
  gatewayListSchema,
  gatewaySchema,
  gatewayTestResultSchema,
  type Company,
  type CompanyCreatePayload,
  type CompanyUpdatePayload,
  type CloseFiscalYearResult,
  type FiscalYear,
  type FiscalYearPayload,
  type FiscalYearPeriod,
  type ForwardFiscalYearResult,
  type OpeningBalancesPayload,
  type OpeningBalancesResult,
  type StorageLocation,
  type StorageLocationPayload,
  type TaxRate,
  type TaxRatePayload,
  type Gateway,
  type GatewayUpdatePayload,
  type GatewayTestResult,
} from "./schemas";

/* ---- company ---- */
export async function fetchCompanies(): Promise<Company[]> {
  const { data } = await api.get("/companies");
  return companyListSchema.parse(data);
}

export async function createCompany(input: CompanyCreatePayload): Promise<Company> {
  const { data } = await api.post("/companies", input);
  return companySchema.parse(data);
}

export async function updateCompany(
  id: string,
  input: CompanyUpdatePayload,
): Promise<Company> {
  const { data } = await api.patch(`/companies/${id}`, input);
  return companySchema.parse(data);
}

export async function fetchCompanyAddresses(companyId: string): Promise<CompanyAddressOut[]> {
  const { data } = await api.get(`/companies/${companyId}/addresses`);
  return companyAddressOutSchema.parse(data) as unknown as CompanyAddressOut[];
}

export async function updateCompanyAddresses(
  companyId: string,
  addresses: any[],
): Promise<CompanyAddressOut[]> {
  const { data } = await api.patch(`/companies/${companyId}/addresses`, { addresses });
  return companyAddressOutSchema.parse(data) as unknown as CompanyAddressOut[];
}

/* ---- tax rates ---- */
export async function fetchTaxRates(): Promise<TaxRate[]> {
  const { data } = await api.get("/taxes");
  return taxRateListSchema.parse(data);
}

export async function createTaxRate(input: TaxRatePayload): Promise<TaxRate> {
  const { data } = await api.post("/taxes", input);
  return taxRateSchema.parse(data);
}

/* ---- storage locations ---- */
export async function fetchStorageLocations(): Promise<StorageLocation[]> {
  const { data } = await api.get("/storage/locations");
  return storageLocationListSchema.parse(data);
}

export async function createStorageLocation(
  input: StorageLocationPayload,
): Promise<StorageLocation> {
  const { data } = await api.post("/storage/locations", input);
  return storageLocationSchema.parse(data);
}

/* ---- fiscal years ---- */
export async function fetchFiscalYears(): Promise<FiscalYear[]> {
  const { data } = await api.get("/fiscal-years");
  return fiscalYearListSchema.parse(data);
}

export async function createFiscalYear(input: FiscalYearPayload): Promise<FiscalYear> {
  const { data } = await api.post("/fiscal-years", input);
  return fiscalYearSchema.parse(data);
}

export async function fetchFiscalYearPeriods(fiscalYearId: string): Promise<FiscalYearPeriod[]> {
  const { data } = await api.get(`/fiscal-years/${fiscalYearId}/periods`);
  return fiscalYearPeriodListSchema.parse(data);
}

export async function closeAccountingPeriod(
  fiscalYearId: string,
  periodId: string,
): Promise<{ id: string; is_open: boolean }> {
  const { data } = await api.post(
    `/fiscal-years/${fiscalYearId}/periods/${periodId}/close`,
  );
  return z.object({ id: z.string(), is_open: z.boolean() }).parse(data);
}

export async function closeFiscalYear(fiscalYearId: string): Promise<CloseFiscalYearResult> {
  const { data } = await api.post(`/fiscal-years/${fiscalYearId}/close`);
  return closeFiscalYearResultSchema.parse(data);
}

export async function forwardFiscalYear(fiscalYearId: string): Promise<ForwardFiscalYearResult> {
  const { data } = await api.post(`/fiscal-years/${fiscalYearId}/forward`);
  return forwardFiscalYearResultSchema.parse(data);
}

/* ---- payment gateways ---- */
export async function fetchGateways(): Promise<Gateway[]> {
  const { data } = await api.get("/payments/gateways");
  return gatewayListSchema.parse(data);
}

export async function updateGateway(
  provider: string,
  input: GatewayUpdatePayload,
): Promise<Gateway> {
  const { data } = await api.put(`/payments/gateways/${provider}`, input);
  return gatewaySchema.parse(data);
}

export async function switchGatewayMode(
  provider: string,
  mode: "test" | "live",
): Promise<Gateway> {
  const { data } = await api.post(`/payments/gateways/${provider}/mode`, { mode });
  return gatewaySchema.parse(data);
}

export async function testGateway(provider: string): Promise<GatewayTestResult> {
  const { data } = await api.post(`/payments/gateways/${provider}/test`);
  return gatewayTestResultSchema.parse(data);
}

/* ---- fiscal years ---- */
export async function postOpeningBalances(
  fiscalYearId: string,
  input: OpeningBalancesPayload,
): Promise<OpeningBalancesResult> {
  const { data } = await api.post(
    `/fiscal-years/${fiscalYearId}/opening-balances`,
    input,
  );
  return openingBalancesResultSchema.parse(data);
}
