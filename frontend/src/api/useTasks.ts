import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type TurnoverTask = Record<string, unknown>;

async function fetchTasks(turnoverId: number): Promise<TurnoverTask[]> {
  const { data } = await api.get<TurnoverTask[]>(`/turnovers/${turnoverId}/tasks`);
  return data;
}

export function useTasks(turnoverId: number | null) {
  return useQuery({
    queryKey: ["tasks", turnoverId],
    queryFn: () => fetchTasks(turnoverId as number),
    enabled: turnoverId !== null,
  });
}
