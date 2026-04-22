import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

/** Unit row from GET /unit-master/ (DB-shaped dict). */
export type UnitMasterUnitRow = Record<string, string | number | boolean | null | undefined>;

type ListEnvelope = {
  success: boolean;
  data: UnitMasterUnitRow[] | null;
  errors: string[];
};

export async function fetchUnitMasterUnits(
  propertyId: number,
  activeOnly: boolean,
): Promise<UnitMasterUnitRow[]> {
  const { data } = await api.get<ListEnvelope>("/unit-master/", {
    params: { property_id: propertyId, active_only: activeOnly },
  });
  if (!data.success) {
    throw new Error(data.errors?.join("; ") || "Failed to load units");
  }
  return Array.isArray(data.data) ? data.data : [];
}

export function useUnitMasterUnits(propertyId: number | null, activeOnly = true) {
  return useQuery({
    queryKey: ["unit-master", propertyId, activeOnly],
    queryFn: () => fetchUnitMasterUnits(propertyId!, activeOnly),
    enabled: propertyId != null && propertyId >= 1,
  });
}
