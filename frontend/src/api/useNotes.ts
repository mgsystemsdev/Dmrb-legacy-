import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type TurnoverNote = Record<string, unknown>;

async function fetchNotes(turnoverId: number): Promise<TurnoverNote[]> {
  const { data } = await api.get<TurnoverNote[]>(`/turnovers/${turnoverId}/notes`);
  return data;
}

export function useNotes(turnoverId: number | null) {
  return useQuery({
    queryKey: ["notes", turnoverId],
    queryFn: () => fetchNotes(turnoverId as number),
    enabled: turnoverId !== null,
  });
}

export async function addNote(
  turnoverId: number,
  propertyId: number,
  severity: string,
  text: string,
) {
  const { data } = await api.post(`/turnovers/${turnoverId}/notes`, {
    severity,
    text,
  }, {
    params: { property_id: propertyId },
  });
  return data;
}

export async function resolveNote(noteId: number) {
  const { data } = await api.patch(`/notes/${noteId}/resolve`);
  return data;
}
