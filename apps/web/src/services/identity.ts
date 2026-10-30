import { api } from "../lib/api-client";

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
  is_active: boolean;
  /** Union of the user's role names across companies. */
  roles?: string[];
}

export interface CompanySummary {
  id: string;
  name: string;
  base_currency: string;
}

export interface MeOut {
  user: UserOut;
  companies: CompanySummary[];
  permissions: string[];
  is_company_admin: boolean;
  /** Assignable role names held for the active company. */
  roles: string[];
}

export interface CompanyOut extends CompanySummary {
  legal_name: string;
  timezone: string;
  locale: string;
  /** Registered address + GSTIN, printed on tax invoices. */
  address?: string | null;
  tax_identifier?: string | null;
}

export async function login(email: string, password: string): Promise<string> {
  const { data } = await api.post<never, { data: { access_token: string } }>(
    "/auth/login",
    { email, password },
  );
  return data.access_token;
}

export async function bootstrap(email: string, password: string, full_name: string): Promise<string> {
  const { data } = await api.post<never, { data: { access_token: string } }>(
    "/auth/bootstrap",
    { email, password, full_name },
  );
  return data.access_token;
}

export interface ShopperRegisterInput {
  slug: string;
  email: string;
  password: string;
  full_name: string;
}

/**
 * Public storefront signup. The store is resolved by its slug, so the new
 * account is created as a shopper of that store (no ERP roles).
 */
export async function registerShopper(
  input: ShopperRegisterInput,
): Promise<{ company_id: string; email: string }> {
  const { data } = await api.post<never, { data: { company_id: string; email: string } }>(
    "/storefront/shop/register",
    input,
  );
  return data;
}

export async function me(): Promise<MeOut> {
  const { data } = await api.get<MeOut>("/auth/me");
  return data;
}

export async function listRoles(): Promise<{ name: string; permissions: string[] }[]> {
  const { data } = await api.get("/roles");
  return data;
}

export function logout(): Promise<void> {
  // Short timeout so sign-out never hangs the redirect to /login.
  return api.post("/auth/logout", null, { timeout: 5000 }).then(() => undefined);
}

export async function createCompany(input: {
  name: string;
  base_currency?: string;
}): Promise<CompanyOut> {
  const { data } = await api.post<CompanyOut>("/companies", input);
  return data;
}

export async function listAllCompanies(): Promise<CompanyOut[]> {
  const { data } = await api.get<CompanyOut[]>("/companies/all");
  return data;
}

/** One company's profile (address/GSTIN for invoice headers). */
export async function getCompany(companyId: string): Promise<CompanyOut> {
  const { data } = await api.get<CompanyOut>(`/companies/${companyId}`);
  return data;
}
