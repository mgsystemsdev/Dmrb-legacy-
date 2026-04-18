import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../api/client";
import {
  useExportManifest,
  useFasRows,
  useMissingMoveOuts,
  useReportDiagnostics,
} from "../api/useOperations";
import { useProperties } from "../api/useProperties";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";
import { formatDate } from "../lib/utils";

type TabKey = "imports" | "repairs" | "exports" | "validator";
type ImportType = "AVAILABLE_UNITS" | "MOVE_OUTS" | "PENDING_MOVE_INS" | "PENDING_FAS";

const IMPORT_TYPES: Array<{ key: ImportType; label: string }> = [
  { key: "AVAILABLE_UNITS", label: "Available Units" },
  { key: "MOVE_OUTS", label: "Move Outs" },
  { key: "PENDING_MOVE_INS", label: "Pending Move-Ins" },
  { key: "PENDING_FAS", label: "Final Account Statements" },
];

export function ReportOperationsPage() {
  const queryClient = useQueryClient();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const propertiesQuery = useProperties();
  const missingMoveOutsQuery = useMissingMoveOuts(propertyId);
  const fasRowsQuery = useFasRows(propertyId);
  const diagnosticsQuery = useReportDiagnostics(propertyId);
  const exportManifestQuery = useExportManifest(propertyId);
  const [activeTab, setActiveTab] = useState<TabKey>("imports");
  const [importType, setImportType] = useState<ImportType>("AVAILABLE_UNITS");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [batchState, setBatchState] = useState<{ batchId: number; status: string } | null>(null);
  const [fasDrafts, setFasDrafts] = useState<Record<number, string>>({});
  const [validatorFile, setValidatorFile] = useState<File | null>(null);
  const [validatorResult, setValidatorResult] = useState<{ summary: { total: number; make_ready: number; service_tech: number }; href: string } | null>(null);

  const propertyName = useMemo(() => {
    const match = propertiesQuery.data?.find((property) => property.property_id === propertyId);
    return match?.property_name ?? match?.name ?? null;
  }, [propertiesQuery.data, propertyId]);

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile || !propertyId) {
        throw new Error("Property and file are required");
      }
      const form = new FormData();
      form.append("property_id", String(propertyId));
      form.append("report_type", importType);
      form.append("file", selectedFile);
      const { data } = await api.post<{
        batch_id: number | null;
        status: string;
      }>("/imports/upload", form);
      return data;
    },
    onSuccess: async (data) => {
      if (data.batch_id) {
        setBatchState({ batchId: data.batch_id, status: data.status });
        if (data.status === "PROCESSING") {
          window.setTimeout(async () => {
            const response = await api.get<{ status: string }>(`/imports/${data.batch_id}/status`);
            setBatchState({ batchId: data.batch_id as number, status: response.data.status });
            await queryClient.invalidateQueries({ queryKey: ["workflow-summary", propertyId] });
            await queryClient.invalidateQueries({ queryKey: ["report-diagnostics", propertyId] });
          }, 2500);
        }
      }
      toast.success("Import started");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Import failed");
    },
  });

  const resolveMissingMoveOutMutation = useMutation({
    mutationFn: async (row: { rowId: number; unitId: number; moveInDate: string | null; moveOutDate: string }) => {
      await api.post(`/operations/report-operations/${propertyId}/missing-move-outs/${row.rowId}/resolve`, {
        unit_id: row.unitId,
        move_out_date: row.moveOutDate,
        move_in_date: row.moveInDate,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["missing-move-outs", propertyId] });
      toast.success("Turnover created");
    },
    onError: () => {
      toast.error("Missing move-out resolution failed");
    },
  });

  const saveFasNoteMutation = useMutation({
    mutationFn: async (rowId: number) => {
      await api.patch(`/operations/report-operations/fas/${rowId}`, {
        note_text: fasDrafts[rowId] ?? "",
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["fas-rows", propertyId] });
      toast.success("FAS note saved");
    },
    onError: () => {
      toast.error("FAS note save failed");
    },
  });

  const validateWorkOrdersMutation = useMutation({
    mutationFn: async () => {
      if (!validatorFile || !propertyId) {
        throw new Error("Property and service request file are required");
      }
      const form = new FormData();
      form.append("property_id", String(propertyId));
      form.append("file", validatorFile);
      const { data } = await api.post<{
        summary: { total: number; make_ready: number; service_tech: number };
        filename: string;
        file_base64: string;
      }>("/operations/work-orders/validate", form);
      const blob = new Blob([Uint8Array.from(atob(data.file_base64), (char) => char.charCodeAt(0))], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      return {
        summary: data.summary,
        href: URL.createObjectURL(blob),
      };
    },
    onSuccess: (data) => {
      setValidatorResult(data);
      toast.success("Work orders classified");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Validation failed");
    },
  });

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: "imports", label: "Import Console" },
    { key: "repairs", label: "Import Reports" },
    { key: "exports", label: "Export Reports" },
    { key: "validator", label: "Work Order Validator" },
  ];

  return (
    <PageShell
      title="Report Operations"
      description="Upload source reports, fix import issues, and download exports."
      action={<PropertySelector />}
    >
      <SectionCard title="Workflow Tabs" description={propertyName ? `Active property: ${propertyName}` : undefined}>
        <div className="tab-group flex-wrap">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`tab-item ${activeTab === tab.key ? "tab-item-active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </SectionCard>

      {activeTab === "imports" ? (
        <SectionCard title="Import Console">
          <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
            <label className="block">
              <span className="label">Report Type</span>
              <select value={importType} onChange={(event) => setImportType(event.target.value as ImportType)} className="input">
                {IMPORT_TYPES.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Upload File</span>
              <input type="file" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} className="input" />
            </label>
            <div className="flex items-end">
              <button type="button" onClick={() => importMutation.mutate()} disabled={importMutation.isPending} className="btn-primary w-full">
                {importMutation.isPending ? "Uploading..." : "Run Import"}
              </button>
            </div>
          </div>
          {batchState ? (
            <div className="mt-5 rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-text">
              Latest batch: #{batchState.batchId} — {batchState.status}
            </div>
          ) : null}
        </SectionCard>
      ) : null}

      {activeTab === "repairs" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="Missing Move-Out Queue" description="Create turnovers from orphaned Pending Move-In rows.">
            <div className="space-y-4">
              {missingMoveOutsQuery.data?.map((row) => (
                <MissingMoveOutForm
                  key={row.row_id}
                  row={row}
                  onResolve={(moveOutDate) =>
                    resolveMissingMoveOutMutation.mutate({
                      rowId: row.row_id,
                      unitId: row.unit_id,
                      moveInDate: row.move_in_date,
                      moveOutDate,
                    })
                  }
                />
              )) ?? <p className="text-sm text-muted">No unresolved missing move-out rows.</p>}
            </div>
          </SectionCard>

          <SectionCard title="FAS Tracker" description="Edit note text stored on the imported FAS rows.">
            <div className="space-y-4">
              {fasRowsQuery.data?.map((row) => (
                <div key={row.row_id} className="rounded-xl border border-border bg-surface-2 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-text-strong">{row.unit_code_norm}</p>
                      <p className="text-sm text-muted">
                        FAS {formatDate(row.fas_date)} imported {formatDate(row.imported_at)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => saveFasNoteMutation.mutate(row.row_id)}
                      className="btn-ghost"
                    >
                      Save Note
                    </button>
                  </div>
                  <textarea
                    value={fasDrafts[row.row_id] ?? row.note_text ?? ""}
                    onChange={(event) => setFasDrafts((current) => ({ ...current, [row.row_id]: event.target.value }))}
                    className="input mt-4 min-h-24"
                  />
                </div>
              )) ?? <p className="text-sm text-muted">No FAS rows available.</p>}
            </div>
          </SectionCard>

          <SectionCard title="Diagnostics" description="Non-OK import rows plus manual override skips.">
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="min-w-full text-sm">
                <thead className="bg-surface-2 text-left text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Unit</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Conflict Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {(diagnosticsQuery.data?.rows ?? []).slice(0, 12).map((row) => (
                    <tr key={row.row_id} className="border-t border-border">
                      <td className="px-4 py-3 font-medium text-text-strong">{row.unit_code_norm ?? row.unit_code_raw ?? "—"}</td>
                      <td className="px-4 py-3 text-text">{row.validation_status}</td>
                      <td className="px-4 py-3 text-text">{row.conflict_reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard title="Override Conflicts" description="Rows skipped because a manual override was kept over the report value.">
            <div className="space-y-3">
              {(diagnosticsQuery.data?.overrides ?? []).slice(0, 10).map((row) => (
                <div key={`${row.row_id}-${row.conflict_field}`} className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                  <p className="font-medium text-text-strong">{row.unit_code_norm}</p>
                  <p className="mt-1 text-sm text-muted">
                    {row.conflict_field}: report value {row.report_value ?? "—"}
                  </p>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "exports" ? (
        <SectionCard title="Export Reports" description="Build files on demand from the board read model.">
          <div className="grid gap-4 md:grid-cols-2">
            {exportManifestQuery.data?.downloads.map((download) => (
              <a
                key={download.key}
                href={download.href}
                className="rounded-xl border border-border bg-surface-2 px-4 py-4 text-sm font-medium text-text transition hover:border-border-strong hover:bg-surface-3"
              >
                {download.label}
              </a>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "validator" ? (
        <SectionCard title="Work Order Validator" description="Upload the active service request file and download the classified workbook.">
          <div className="grid gap-4 md:grid-cols-[1fr_auto]">
            <input type="file" onChange={(event) => setValidatorFile(event.target.files?.[0] ?? null)} className="input" />
            <button
              type="button"
              onClick={() => validateWorkOrdersMutation.mutate()}
              disabled={validateWorkOrdersMutation.isPending}
              className="btn-primary"
            >
              {validateWorkOrdersMutation.isPending ? "Validating..." : "Validate"}
            </button>
          </div>
          {validatorResult ? (
            <div className="mt-5 rounded-xl border border-border bg-surface-2 p-4">
              <p className="text-sm text-text">
                Total {validatorResult.summary.total} | Make Ready {validatorResult.summary.make_ready} | Service Technician {validatorResult.summary.service_tech}
              </p>
              <a href={validatorResult.href} download="validated_work_orders.xlsx" className="btn-primary mt-3">
                Download Classified Workbook
              </a>
            </div>
          ) : null}
        </SectionCard>
      ) : null}
    </PageShell>
  );
}

function MissingMoveOutForm({
  row,
  onResolve,
}: {
  row: { row_id: number; unit_code_norm: string; move_in_date: string | null; batch_created_at: string; unit_id: number };
  onResolve: (moveOutDate: string) => void;
}) {
  const [moveOutDate, setMoveOutDate] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!moveOutDate) {
      return;
    }
    onResolve(moveOutDate);
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-surface-2 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-medium text-text-strong">{row.unit_code_norm}</p>
          <p className="text-sm text-muted">
            Move-In {formatDate(row.move_in_date)} | Detected {formatDate(row.batch_created_at)}
          </p>
        </div>
        <div className="flex gap-3">
          <input
            type="date"
            value={moveOutDate}
            onChange={(event) => setMoveOutDate(event.target.value)}
            className="input"
          />
          <button type="submit" className="btn-primary">
            Create Turnover
          </button>
        </div>
      </div>
    </form>
  );
}
