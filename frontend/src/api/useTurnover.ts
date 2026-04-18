import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type TurnoverTask = {
  task_id: number;
  task_type: string;
  execution_status: string;
  assignee: string | null;
  vendor_due_date: string | null;
  scheduled_date: string | null;
  required: boolean;
  blocking: boolean;
  completed_date: string | null;
};

export type TurnoverRisk = {
  risk_id: number;
  risk_type: string;
  severity: string;
  opened_at: string | null;
  resolved_at: string | null;
};

export type TurnoverDetailResponse = {
  turnover: Record<string, unknown>;
  unit: Record<string, unknown> | null;
  tasks: TurnoverTask[];
  readiness: {
    state: string;
    completed: number;
    total: number;
  };
  sla: {
    risk_level: string;
    severity: string;
    days_until_breach: number | null;
    move_in_pressure: number | null;
  };
  days_to_be_ready: number | null;
  is_open: boolean;
  risks: TurnoverRisk[];
};

async function fetchTurnover(turnoverId: number): Promise<TurnoverDetailResponse> {
  const { data } = await api.get<TurnoverDetailResponse>(`/turnovers/${turnoverId}/detail`);
  return data;
}

export function useTurnover(turnoverId: number | null) {
  return useQuery({
    queryKey: ["turnover", turnoverId],
    queryFn: () => fetchTurnover(turnoverId as number),
    enabled: turnoverId !== null,
  });
}
