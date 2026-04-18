import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type WorkflowSummary = {
  today: string;
  summary: {
    total: number;
    by_priority: Record<string, number>;
    by_phase: Record<string, number>;
    by_readiness: Record<string, number>;
  };
  metrics: {
    active: number;
    violations: number;
    plan_breach: number;
    sla_breach: number;
    move_in_risk: number;
    work_stalled: number;
  };
  risk_metrics: {
    vacant_over_7: number;
    sla_breach: number;
    move_in_soon: number;
  };
  critical_units: Array<{
    unit_code: string;
    event: string;
    date: string;
    turnover_id: number;
  }>;
  import_timestamps: Record<string, string | null>;
  missing_move_outs: MissingMoveOutRow[];
};

export type RiskRow = {
  unit_code: string;
  phase_code: string;
  phase_id: number | null;
  risk_level: "HIGH" | "MEDIUM" | "LOW";
  risk_score: number;
  risk_reasons: string[];
  move_in_date: string | null;
};

export type MissingMoveOutRow = {
  row_id: number;
  unit_id: number;
  unit_code_norm: string;
  report_type: string;
  batch_created_at: string;
  move_in_date: string | null;
  conflict_reason: string;
};

export type FasRow = {
  row_id: number;
  unit_code_norm: string;
  fas_date: string | null;
  note_text: string | null;
  imported_at: string;
  report_type: string;
};

export type DiagnosticRow = {
  row_id: number;
  unit_code_raw?: string | null;
  unit_code_norm?: string | null;
  validation_status: string;
  conflict_reason: string | null;
  report_type?: string | null;
  created_at?: string | null;
};

export type OverrideConflictRow = {
  row_id: number;
  unit_code_norm: string;
  validation_status: string;
  conflict_reason: string | null;
  report_type: string;
  conflict_field: string;
  report_value: string | null;
  turnover_id: number;
  detected_at: string;
};

export type ImportBatchHistory = {
  batch_id: number;
  report_type: string;
  status: string;
  record_count: number;
  created_at: string;
};

export type ReportDiagnosticsResponse = {
  batches: ImportBatchHistory[];
  rows: DiagnosticRow[];
  overrides: OverrideConflictRow[];
};

export type PropertyStructureResponse = {
  structure: Array<{
    phase: {
      phase_id: number;
      phase_code: string;
      name?: string | null;
    };
    buildings: Array<{
      building: {
        building_id: number;
        building_code: string;
        name?: string | null;
      };
      units: Array<{
        unit_id: number;
        unit_code_norm: string;
        is_active?: boolean;
        has_carpet?: boolean;
        has_wd_expected?: boolean;
      }>;
    }>;
  }>;
};

export type AdminUser = {
  user_id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ExportManifest = {
  downloads: Array<{
    key: string;
    label: string;
    href: string;
  }>;
};

export type FlagBridgeItem = {
  turnover: {
    turnover_id: number;
    move_in_date: string | null;
    report_ready_date: string | null;
    days_since_move_out: number | null;
    lifecycle_phase: string;
  };
  unit: {
    unit_code_norm: string;
    phase_code?: string | null;
    phase_name?: string | null;
  } | null;
  agreements?: Record<string, string>;
};

async function fetchWorkflowSummary(propertyId: number): Promise<WorkflowSummary> {
  const { data } = await api.get<WorkflowSummary>(`/operations/workflow/${propertyId}`);
  return data;
}

async function fetchRiskRows(propertyId: number): Promise<RiskRow[]> {
  const { data } = await api.get<{ rows: RiskRow[] }>(`/operations/risk/${propertyId}`);
  return data.rows;
}

async function fetchMissingMoveOuts(propertyId: number): Promise<MissingMoveOutRow[]> {
  const { data } = await api.get<{ rows: MissingMoveOutRow[] }>(
    `/operations/report-operations/${propertyId}/missing-move-outs`,
  );
  return data.rows;
}

async function fetchFasRows(propertyId: number): Promise<FasRow[]> {
  const { data } = await api.get<{ rows: FasRow[] }>(`/operations/report-operations/${propertyId}/fas`);
  return data.rows;
}

async function fetchReportDiagnostics(propertyId: number): Promise<ReportDiagnosticsResponse> {
  const { data } = await api.get<ReportDiagnosticsResponse>(
    `/operations/report-operations/${propertyId}/diagnostics`,
  );
  return data;
}

async function fetchAdminSettings(): Promise<{ enable_db_write: boolean }> {
  const { data } = await api.get<{ enable_db_write: boolean }>("/operations/admin/settings");
  return data;
}

async function fetchFlagBridge(propertyId: number): Promise<{ rows: FlagBridgeItem[]; metrics: { total: number; violations: number; units_with_breach: number } }> {
  const { data } = await api.get<{ rows: FlagBridgeItem[]; metrics: { total: number; violations: number; units_with_breach: number } }>(
    `/operations/flag-bridge/${propertyId}`,
  );
  return data;
}

async function fetchPropertyStructure(propertyId: number): Promise<PropertyStructureResponse> {
  const { data } = await api.get<PropertyStructureResponse>(
    `/operations/admin/property-structure/${propertyId}`,
  );
  return data;
}

async function fetchAdminUsers(): Promise<AdminUser[]> {
  const { data } = await api.get<{ rows: AdminUser[] }>("/operations/admin/users");
  return data.rows;
}

async function fetchExportManifest(propertyId: number): Promise<ExportManifest> {
  const { data } = await api.get<ExportManifest>(`/operations/exports/${propertyId}/manifest`);
  return data;
}

export function useWorkflowSummary(propertyId: number | null) {
  return useQuery({
    queryKey: ["workflow-summary", propertyId],
    queryFn: () => fetchWorkflowSummary(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useRiskRows(propertyId: number | null) {
  return useQuery({
    queryKey: ["risk-rows", propertyId],
    queryFn: () => fetchRiskRows(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useMissingMoveOuts(propertyId: number | null) {
  return useQuery({
    queryKey: ["missing-move-outs", propertyId],
    queryFn: () => fetchMissingMoveOuts(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useFasRows(propertyId: number | null) {
  return useQuery({
    queryKey: ["fas-rows", propertyId],
    queryFn: () => fetchFasRows(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useReportDiagnostics(propertyId: number | null) {
  return useQuery({
    queryKey: ["report-diagnostics", propertyId],
    queryFn: () => fetchReportDiagnostics(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useAdminSettings(enabled: boolean) {
  return useQuery({
    queryKey: ["admin-settings"],
    queryFn: fetchAdminSettings,
    enabled,
  });
}

export function useFlagBridge(propertyId: number | null) {
  return useQuery({
    queryKey: ["flag-bridge", propertyId],
    queryFn: () => fetchFlagBridge(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function usePropertyStructure(propertyId: number | null) {
  return useQuery({
    queryKey: ["property-structure", propertyId],
    queryFn: () => fetchPropertyStructure(propertyId as number),
    enabled: propertyId !== null,
  });
}

export function useAdminUsers(enabled: boolean) {
  return useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchAdminUsers,
    enabled,
  });
}

export function useExportManifest(propertyId: number | null) {
  return useQuery({
    queryKey: ["export-manifest", propertyId],
    queryFn: () => fetchExportManifest(propertyId as number),
    enabled: propertyId !== null,
  });
}
