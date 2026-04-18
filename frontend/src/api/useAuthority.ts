import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type AuthorityRow = {
  field: string;
  current_value: string;
  source: string;
};

async function fetchAuthority(turnoverId: number): Promise<{ rows: AuthorityRow[] }> {
  const { data } = await api.get<{ rows: AuthorityRow[] }>(`/turnovers/${turnoverId}/authority`);
  return data;
}

export function useAuthority(turnoverId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ["turnover-authority", turnoverId],
    queryFn: () => fetchAuthority(turnoverId as number),
    enabled: enabled && turnoverId !== null,
  });
}
