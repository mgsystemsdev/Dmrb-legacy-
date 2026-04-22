import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

/** Query key prefix for unit list; use for targeted invalidation. */
export const unitsQueryKeyRoot = ["units"] as const;

/** Unit row from GET /unit-master/ (includes joined ``unit_code``, ``phase_name``, ``building_name``). */
export type UnitRow = Record<string, string | number | boolean | null | undefined>;

/** @deprecated Use UnitRow */
export type UnitMasterUnitRow = UnitRow;

type ListEnvelope = {
  success: boolean;
  data: UnitRow[] | null;
  errors: string[];
};

export type ImportUnitsResponse = {
  success: boolean;
  data: { created: number; skipped: number; errors: string[] } | null;
  errors: string[];
};

export type CreateUnitBody = {
  unit_code: string;
  phase_id: number | null;
  building_id: number | null;
  floor_plan: string | null;
  gross_sq_ft: number | null;
  has_carpet: boolean;
  has_wd_expected: boolean;
};

type CreateEnvelope = {
  success: boolean;
  data: UnitRow | null;
  errors: string[];
};

export async function fetchUnits(propertyId: number, activeOnly: boolean): Promise<UnitRow[]> {
  const { data } = await api.get<ListEnvelope>("/unit-master/", {
    params: { property_id: propertyId, active_only: activeOnly },
  });
  if (!data.success) {
    throw new Error(data.errors?.join("; ") || "Failed to load units");
  }
  return Array.isArray(data.data) ? data.data : [];
}

/**
 * GET /api/unit-master/?property_id=…&active_only=…
 */
export function useUnits(propertyId: number | null, options?: { activeOnly?: boolean }) {
  const activeOnly = options?.activeOnly ?? true;
  return useQuery({
    queryKey: [...unitsQueryKeyRoot, propertyId, activeOnly],
    queryFn: () => fetchUnits(propertyId!, activeOnly),
    enabled: propertyId != null && propertyId >= 1,
  });
}

export type ImportUnitsVariables = {
  propertyId: number;
  file: File;
  strict?: boolean;
};

/**
 * POST /api/unit-master/import (multipart FormData).
 */
export function useImportUnits() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ImportUnitsVariables) => {
      const form = new FormData();
      form.append("property_id", String(input.propertyId));
      form.append("strict", String(input.strict ?? false));
      form.append("file", input.file);
      const { data } = await api.post<ImportUnitsResponse>("/unit-master/import", form);
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [...unitsQueryKeyRoot, variables.propertyId],
      });
    },
  });
}

export type CreateUnitVariables = {
  propertyId: number;
  body: CreateUnitBody;
};

/**
 * POST /api/unit-master/?property_id=…
 */
export function useCreateUnit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateUnitVariables) => {
      const { data } = await api.post<CreateEnvelope>(
        `/unit-master/?property_id=${input.propertyId}`,
        input.body,
      );
      if (!data.success) {
        throw new Error(data.errors?.join("; ") || "Create unit failed");
      }
      return data.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [...unitsQueryKeyRoot, variables.propertyId],
      });
    },
  });
}
