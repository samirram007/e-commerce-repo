/** Display formatting helpers. All money/quantity values arrive from the API as decimal strings. */

/** Currency used when a value arrives without one (companies default to INR). */
export const DEFAULT_CURRENCY = "INR";

/** Currency symbols shown in the UI (falls back to the code for unknown ones). */
const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
  AUD: "A$",
  CAD: "C$",
  ZAR: "R",
};

/** Symbol for a currency code (e.g. "INR" → "₹"). */
export function currencySymbol(currency?: string | null): string {
  const code = (currency ?? DEFAULT_CURRENCY).toUpperCase();
  return CURRENCY_SYMBOLS[code] ?? code;
}

export function formatMoney(value: string | number | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  const code = (currency ?? DEFAULT_CURRENCY).toUpperCase();
  const symbol = CURRENCY_SYMBOLS[code] ?? code;
  // Indian numbering (1,23,456.00) for INR, locale grouping elsewhere.
  const locale = code === "INR" ? "en-IN" : undefined;
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
  return `${symbol}${formatted}`;
}

export function formatQty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(n);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString();
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export type Tone = "default" | "ok" | "warn" | "bad";

const OK = new Set([
  "paid",
  "posted",
  "completed",
  "approved",
  "delivered",
  "done",
  "active",
  "succeeded",
  "receipt",
  "closed",
  "received",
  "balanced",
  "confirmed",
  "resalable",
]);
const WARN = new Set([
  "pending",
  "pending_payment",
  "draft",
  "submitted",
  "requested",
  "open",
  "partially_received",
  "in_transit",
  "dispatched",
  "out_for_delivery",
  "processing",
  "unpaid",
  "partial",
]);
const BAD = new Set([
  "cancelled",
  "canceled",
  "rejected",
  "reversed",
  "failed",
  "void",
  "inactive",
  "error",
  "damaged",
  "quarantine",
]);

export function statusTone(status: string | null | undefined): Tone {
  const s = (status ?? "").toLowerCase();
  if (OK.has(s)) return "ok";
  if (BAD.has(s)) return "bad";
  if (WARN.has(s)) return "warn";
  return "default";
}
