import { z } from "zod";

export const auditRowSchema = z.object({
  id: z.string(),
  company_id: z.string().nullable(),
  actor_user_id: z.string().nullable(),
  action: z.string(),
  entity_type: z.string(),
  entity_id: z.string().nullable(),
  before_data: z.string().nullable(),
  after_data: z.string().nullable(),
  created_at: z.string(),
});
export type AuditRow = z.infer<typeof auditRowSchema>;

export interface AuditFilters {
  limit?: number;
  offset?: number;
}
