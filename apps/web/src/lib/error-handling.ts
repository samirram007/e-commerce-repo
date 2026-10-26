/**
 * Central API error handling.
 *
 * The axios layer rejects with an `ApiError` mirroring the backend envelope
 * (`{ error: { code, message, details } }`), so UI code can branch on a stable
 * shape instead of poking at Axios internals. `toApiError` normalizes anything
 * that can be thrown (including unknown values and plain Errors).
 */

export interface ApiErrorInfo {
  code: string;
  message: string;
  status: number;
  details?: unknown;
}

export const NETWORK_ERROR = "NETWORK_ERROR";
export const UNKNOWN_ERROR = "UNKNOWN_ERROR";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;

  constructor(init: { code: string; message: string; status: number; details?: unknown }) {
    super(init.message);
    this.name = "ApiError";
    this.code = init.code;
    this.status = init.status;
    this.details = init.details;
  }
}

/** Structural check so plain `{ code, message }` objects still pass. */
export function isApiError(e: unknown): e is ApiErrorInfo {
  if (e instanceof ApiError) return true;
  return typeof e === "object" && e !== null && "code" in e && "message" in e;
}

/** Normalize any thrown value into a stable `{ code, message, status }`. */
export function toApiError(e: unknown): ApiErrorInfo {
  if (e instanceof ApiError) {
    return { code: e.code, message: e.message, status: e.status, details: e.details };
  }
  if (e instanceof Error) {
    return { code: UNKNOWN_ERROR, message: e.message, status: 0 };
  }
  if (typeof e === "object" && e !== null && "code" in e && "message" in e) {
    const info = e as { code: unknown; message: unknown; status?: unknown; details?: unknown };
    return {
      code: String(info.code),
      message: String(info.message),
      status: typeof info.status === "number" ? info.status : 0,
      details: info.details,
    };
  }
  return { code: UNKNOWN_ERROR, message: "Unexpected error", status: 0 };
}

export function errorMessage(e: unknown): string {
  return toApiError(e).message;
}

export function errorCode(e: unknown): string {
  return toApiError(e).code;
}

export function isUnauthorized(e: unknown): boolean {
  return toApiError(e).status === 401;
}

export function isForbidden(e: unknown): boolean {
  return toApiError(e).status === 403;
}

export function isNotFound(e: unknown): boolean {
  return toApiError(e).status === 404;
}
