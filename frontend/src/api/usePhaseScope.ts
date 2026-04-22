import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export type PropertyPhase = {
  phase_id: number;
  phase_code: string;
  name?: string | null;
};

type PhaseScopeData = {
  property_id: number;
  phase_ids: number[];
};

type StructuredResponse<T> = {
  success: boolean;
  data: T;
  errors: string[];
};

/**
 * GET /api/properties/{propertyId}/phases
 */
export function usePropertyPhases(propertyId: number | null) {
  return useQuery({
    queryKey: ["property-phases", propertyId],
    queryFn: async () => {
      const res = await api.get<PropertyPhase[]>(`/properties/${propertyId}/phases`);
      return res.data;
    },
    enabled: propertyId != null && propertyId >= 1,
  });
}

/**
 * GET /api/phase-scope?property_id=
 */
export function usePhaseScopeForProperty(propertyId: number | null) {
  return useQuery({
    queryKey: ["phase-scope", propertyId],
    queryFn: async () => {
      const res = await api.get<StructuredResponse<PhaseScopeData>>("/phase-scope", {
        params: { property_id: propertyId },
      });
      const body = res.data;
      if (!body.success) {
        throw new Error(body.errors[0] ?? "Could not load phase scope");
      }
      return body.data;
    },
    enabled: propertyId != null && propertyId >= 1,
  });
}

type PutInput = { propertyId: number; phaseIds: number[] };

/**
 * PUT /api/phase-scope
 */
export function useUpdatePhaseScope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PutInput) => {
      const res = await api.put<StructuredResponse<PhaseScopeData | null>>("/phase-scope", {
        property_id: input.propertyId,
        phase_ids: input.phaseIds,
      });
      const body = res.data;
      if (!body.success) {
        throw new Error(body.errors[0] ?? "Could not save phase scope");
      }
      if (body.data == null) {
        throw new Error("Invalid response from server");
      }
      return body.data;
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["phase-scope", variables.propertyId] });
    },
  });
}
