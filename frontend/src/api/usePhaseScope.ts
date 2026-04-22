import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
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

type ScopedPropertyPhasesResult = {
  /** Phases in scope for this property, or `undefined` while either query is loading / disabled. */
  filteredPhases: PropertyPhase[] | undefined;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
};

/**
 * Single source for phase dropdowns: `usePropertyPhases` filtered by
 * `usePhaseScopeForProperty` `phase_ids`. If the user has no separate scope row, the
 * server returns all phase ids, so the result is the full catalog. While either query
 * is loading, `filteredPhases` is `undefined`.
 */
export function useScopedPropertyPhases(propertyId: number | null): ScopedPropertyPhasesResult {
  const phasesQuery = usePropertyPhases(propertyId);
  const scopeQuery = usePhaseScopeForProperty(propertyId);

  const filteredPhases = useMemo((): PropertyPhase[] | undefined => {
    if (propertyId == null || propertyId < 1) {
      return undefined;
    }
    const all = phasesQuery.data;
    const scope = scopeQuery.data;
    if (all == null || scope == null) {
      return undefined;
    }
    const allowed = new Set(scope.phase_ids);
    return all.filter((p) => allowed.has(p.phase_id));
  }, [phasesQuery.data, propertyId, scopeQuery.data]);

  const isPending = Boolean(
    propertyId != null && propertyId >= 1 && (phasesQuery.isPending || scopeQuery.isPending),
  );
  const isError = phasesQuery.isError || scopeQuery.isError;
  const error = (phasesQuery.error ?? scopeQuery.error) as Error | null;

  return { filteredPhases, isPending, isError, error };
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
