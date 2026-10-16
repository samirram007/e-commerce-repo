import axios from "axios";
import { clearSession, emitUnauthorized, setAccessToken } from "../auth/session";
import { clearSensitiveCaches } from "../lib/query-client";
import { setSession } from "../auth/session-store";
import { listAllCompanies, me as meRequest, type MeOut } from "./identity";

export const identityApi = {
  async login(email: string, password: string): Promise<string> {
    const token = await (await import("./identity")).login(email, password);
    setAccessToken(token);
    const profile = await meRequest();
    const companies = profile.companies.length > 0 ? profile.companies : await listAllCompanies().catch(() => []);
    setSession({ me: { ...profile, companies }, companyId: companies[0]?.id ?? null, status: "authenticated" });
    return token;
  },

  async bootstrap(email: string, password: string, fullName: string): Promise<string> {
    const { bootstrap } = await import("./identity");
    const token = await bootstrap(email, password, fullName);
    setAccessToken(token);
    const profile = await meRequest();
    setSession({ me: profile, companyId: profile.companies[0]?.id ?? null, status: "authenticated" });
    return token;
  },

  /** Silent refresh using the httpOnly cookie; null when it fails. */
  async tryRefreshToken(): Promise<string | null> {
    try {
      const { data } = await axios.post<{ access_token: string }>("/api/v1/auth/refresh", null, {
        withCredentials: true,
      });
      setAccessToken(data.access_token);
      const profile = await meRequest();
      const companies = profile.companies.length > 0 ? profile.companies : await listAllCompanies().catch(() => []);
      setSession({ me: { ...profile, companies }, companyId: companies[0]?.id ?? null, status: "authenticated" });
      return data.access_token;
    } catch {
      return null;
    }
  },

  async refreshMe(): Promise<MeOut | null> {
    try {
      return await meRequest();
    } catch {
      return null;
    }
  },

  async logout(): Promise<void> {
    try {
      const { logout } = await import("./identity");
      await logout();
    } finally {
      clearSession();
      clearSensitiveCaches();
      setSession({ me: null, companyId: null, status: "guest" });
    }
  },

  emitUnauthorized,
};
