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

/** Per-row report from validation / dry-run (mirrors backend). */
export type UnitMasterImportRowReport = {
  row_index: number;
  unit_code: string | null;
  status: "valid" | "warning" | "error";
  messages: string[];
  /** Stable JSON string per simulated action, sorted keys (backend). */
  actions: string[];
};

/** Row-level validation + simulation (dry-run 200, or 422 pre-import gate). */
export type UnitMasterImportReport = {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  warning_rows: number;
  error_rows: number;
  file_messages: string[];
  rows: UnitMasterImportRowReport[];
  has_blocking_errors: boolean;
};

/**
 * Coerce an API payload into a stable `UnitMasterImportReport` (same for 200 and 422).
 * Does not mutate the input. Row counts are derived from normalized row status values.
 */
export function coalesceUnitMasterImportReport(
  input: unknown,
  dryRun: boolean,
): UnitMasterImportReport {
  const o = input && typeof input === "object" ? (input as Record<string, unknown>) : {};
  const fileRaw = o.file_messages;
  const file_messages = Array.isArray(fileRaw) ? fileRaw.map((x) => String(x)) : [];
  const rawRows = Array.isArray(o.rows) ? o.rows : [];

  const rows: UnitMasterImportRowReport[] = rawRows.map((row, i) => {
    const r = row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const rawUnit = r.unit_code;
    const unit_code =
      rawUnit === null || rawUnit === undefined || String(rawUnit).trim() === ""
        ? null
        : String(rawUnit);
    const st = r.status;
    const status: UnitMasterImportRowReport["status"] =
      st === "valid" || st === "warning" || st === "error" ? st : "error";
    const rawMsgs = r.messages;
    let messages: string[] = [];
    if (Array.isArray(rawMsgs)) {
      messages = rawMsgs.map((m) => String(m)).filter((m) => m.length > 0);
    } else if (rawMsgs != null) {
      messages = [String(rawMsgs)];
    }
    const rawAct = r.actions;
    const actions: string[] = [];
    if (Array.isArray(rawAct)) {
      for (const a of rawAct) {
        if (typeof a === "string") {
          actions.push(a);
        } else {
          actions.push(JSON.stringify(a));
        }
      }
    }
    if (status === "valid") {
      messages = [];
    } else if ((status === "warning" || status === "error") && messages.length === 0) {
      messages = [`(${status}: no detail message)`];
    }
    let row_index = i;
    if (typeof r.row_index === "number" && !Number.isNaN(r.row_index)) {
      row_index = r.row_index;
    }
    return { row_index, unit_code, status, messages, actions };
  });

  const valid_rows = rows.filter((x) => x.status === "valid").length;
  const warning_rows = rows.filter((x) => x.status === "warning").length;
  const error_rows = rows.filter((x) => x.status === "error").length;
  return {
    dry_run: dryRun,
    total_rows: rows.length,
    valid_rows,
    warning_rows,
    error_rows,
    file_messages,
    rows,
    has_blocking_errors: error_rows > 0,
  };
}

export type UnitMasterImportCommitData = {
  dry_run: false;
  created: number;
  skipped: number;
  errors: string[];
};

export type ImportUnitsResponse = {
  success: boolean;
  data: UnitMasterImportReport | UnitMasterImportCommitData | null;
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
  /** If true, returns validation + simulated actions only (no DB writes). */
  dryRun?: boolean;
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
      form.append("dry_run", String(input.dryRun ?? false));
      form.append("file", input.file);
      const { data } = await api.post<ImportUnitsResponse>("/unit-master/import", form);
      return data;
    },
    onSuccess: (data, variables) => {
      const d = data.data;
      if (d && "rows" in d && "dry_run" in d && d.dry_run) {
        return;
      }
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
