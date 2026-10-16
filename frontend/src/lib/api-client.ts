import axios, { AxiosError, type AxiosInstance } from "axios";
import { clearSession, emitUnauthorized, getAccessToken } from "../auth/session";
import { getSession } from "../auth/session-store";
import { ApiError, NETWORK_ERROR } from "./error-handling";

/**
 * Configured Axios instance for the JSON API.
 *
 * - Base URL is relative (`/api/v1`) so dev traffic flows through the Vite proxy.
 * - Injects the Bearer access token and the `X-Company-Id` scoping header.
 * - Transparently refreshes once on a 401 (httpOnly refresh cookie) and retries.
 * - Rejects with an `ApiError` carrying the backend error envelope.
 */
export const api: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  timeout: 15000,
  withCredentials: true, // refresh-token cookie
});

/** Descriptive alias for callers that prefer `axiosClient`. */
export const axiosClient = api;

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // Company scoping: the backend is authoritative and resolves this header via
  // current_company_ctx, but it must be present on every request.
  const companyId = getSession().companyId;
  if (companyId) config.headers["X-Company-Id"] = companyId;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post("/api/v1/auth/refresh", null, { withCredentials: true })
      .then((r) => r.data.access_token as string)
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ErrorEnvelope>) => {
    const original = error.config as (typeof error.config & { _retried?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      const token = await tryRefresh();
      if (token) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${token}`;
        return api.request(original);
      }
      clearSession();
      emitUnauthorized();
    }
    const body = error.response?.data?.error;
    return Promise.reject(
      new ApiError({
        code: body?.code ?? NETWORK_ERROR,
        message: body?.message ?? error.message,
        status: error.response?.status ?? 0,
        details: body?.details,
      }),
    );
  },
);

// Back-compat re-exports: many modules import these from `lib/api-client`.
export { ApiError, errorMessage, isApiError, isForbidden, isNotFound, isUnauthorized, toApiError } from "./error-handling";
export type { ApiErrorInfo } from "./error-handling";
