import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type AuditEntry = {
  audit_id?: number;
  changed_at: string | null;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  actor: string | null;
  source: string | null;
};

async function fetchAudit(turnoverId: number): Promise<AuditEntry[]> {
  const { data } = await api.get<AuditEntry[]>(`/turnovers/${turnoverId}/audit`);
  return data;
}

export function useAudit(turnoverId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ["turnover-audit", turnoverId],
    queryFn: () => fetchAudit(turnoverId as number),
    enabled: enabled && turnoverId !== null,
  });
}
