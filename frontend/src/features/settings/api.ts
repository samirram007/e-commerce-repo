import { api } from "../../lib/api-client";
import {
  companyListSchema,
  companySchema,
  fiscalYearListSchema,
  fiscalYearSchema,
  storageLocationListSchema,
  storageLocationSchema,
  taxRateListSchema,
  taxRateSchema,
  type Company,
  type CompanyCreatePayload,
  type CompanyUpdatePayload,
  type FiscalYear,
  type FiscalYearPayload,
  type StorageLocation,
  type StorageLocationPayload,
  type TaxRate,
  type TaxRatePayload,
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
