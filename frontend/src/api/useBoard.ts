import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type BoardTask = {
  task_id: number;
  task_type: string;
  execution_status: string;
  assignee: string | null;
  vendor_due_date: string | null;
  scheduled_date: string | null;
  manager_confirmed_at: string | null;
};

export type BoardRow = {
  turnover_id: number;
  unit_id: number | null;
  unit_code: string;
  phase_id: number | null;
  phase_code: string | null;
  phase: string;
  status: string;
  nvm: string;
  qc: string;
  alert: string;
  move_out_date: string | null;
  report_ready_date: string | null;
  lifecycle_phase: string;
  readiness: string;
  priority: string;
  days_since_move_out: number | null;
  days_to_move_in: number | null;
  days_to_be_ready: number | null;
  move_in_date: string | null;
  notes_summary: string;
  task_completion: [number, number];
  agreements: Record<string, string>;
  tasks: BoardTask[];
};

export type BoardResponse = {
  property_id: number;
  as_of: string;
  rows: BoardRow[];
  task_types_present: string[];
  total: number;
};

type BoardFilters = {
  phase?: string;
  search?: string;
  status?: string;
  nvm?: string;
  qc?: string;
  board_filter?: string;
};

async function fetchBoard(propertyId: number, filters: BoardFilters): Promise<BoardResponse> {
  const { data } = await api.get<BoardResponse>(`/board/${propertyId}`, {
    params: filters,
  });
  return data;
}

export function useBoard(propertyId: number | null, filters: BoardFilters = {}) {
  return useQuery({
    queryKey: ["board", propertyId, filters],
    queryFn: () => fetchBoard(propertyId as number, filters),
    enabled: propertyId !== null,
  });
}
