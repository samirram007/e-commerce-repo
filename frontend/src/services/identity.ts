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

export async function me(): Promise<MeOut> {
  const { data } = await api.get<MeOut>("/auth/me");
  return data;
}

export async function listRoles(): Promise<{ name: string; permissions: string[] }[]> {
  const { data } = await api.get("/roles");
  return data;
}

export function logout(): Promise<void> {
  return api.post("/auth/logout").then(() => undefined);
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
