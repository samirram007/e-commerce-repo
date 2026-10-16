import type { ZodError } from "zod";

/** Flatten a zod error into `{ "field.path": "message" }` keyed by the first issue per path. */
export function fieldErrors(error: ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = issue.path.length > 0 ? issue.path.join(".") : "_";
    if (!out[key]) out[key] = issue.message;
  }
  return out;
}
