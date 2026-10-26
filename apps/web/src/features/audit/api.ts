import { z } from "zod";
import { api } from "../../lib/api-client";
import { auditRowSchema, type AuditFilters, type AuditRow } from "./schemas";

export async function fetchAudit(filters: AuditFilters = {}): Promise<AuditRow[]> {
  const { data } = await api.get("/audit", {
    params: { limit: filters.limit, offset: filters.offset },
  });
  return z.array(auditRowSchema).parse(data);
}
