import { queryOptions } from "@tanstack/react-query";
import { fetchAudit } from "./api";
import type { AuditFilters } from "./schemas";

export const auditKeys = {
  all: ["audit"] as const,
  list: (filters: AuditFilters) => [...auditKeys.all, "list", filters] as const,
};

export function auditQueryOptions(filters: AuditFilters = {}) {
  return queryOptions({
    queryKey: auditKeys.list(filters),
    queryFn: () => fetchAudit(filters),
  });
}
