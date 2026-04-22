import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import axios from "axios";
import { toast } from "sonner";
import { api } from "../api/client";
import { useUnitMasterUnits, type UnitMasterUnitRow } from "../api/useUnitMaster";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";

type ImportSuccessBody = {
  success: boolean;
  data: { created: number } | null;
  errors: string[];
};

function formatAxiosMessage(error: unknown): string {
  if (axios.isAxiosError(error) && error.response?.data && typeof error.response.data === "object") {
    const body = error.response.data as { errors?: string[]; detail?: string | string[] };
    if (Array.isArray(body.errors) && body.errors.length) {
      return body.errors.join("; ");
    }
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map(String).join("; ");
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed";
}

export function UnitMasterPage() {
  const queryClient = useQueryClient();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const [activeOnly, setActiveOnly] = useState(true);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [strictImport, setStrictImport] = useState(false);

  const unitsQuery = useUnitMasterUnits(propertyId, activeOnly);

  const invalidateUnits = () =>
    queryClient.invalidateQueries({ queryKey: ["unit-master", propertyId] });

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!propertyId || !importFile) {
        throw new Error("Select a property and a CSV file");
      }
      const form = new FormData();
      form.append("property_id", String(propertyId));
      form.append("strict", String(strictImport));
      form.append("file", importFile);
      const { data } = await api.post<ImportSuccessBody>("/unit-master/import", form);
      return data;
    },
    onSuccess: async (data) => {
      if (!data.success) {
        toast.error(data.errors?.join("; ") || "Import failed");
        return;
      }
      const created = data.data?.created ?? 0;
      toast.success(`Import complete — ${created} unit(s) created`);
      setImportFile(null);
      await invalidateUnits();
    },
    onError: (error) => {
      toast.error(formatAxiosMessage(error));
    },
  });

  const colDefs = useMemo<ColDef<UnitMasterUnitRow>[]>(
    () => [
      { field: "unit_id", headerName: "ID", width: 90, filter: true },
      { field: "unit_code_norm", headerName: "Unit", minWidth: 110, filter: true },
      { field: "unit_code_raw", headerName: "Raw code", minWidth: 110, filter: true },
      { field: "phase_id", headerName: "Phase ID", width: 110 },
      { field: "building_id", headerName: "Building ID", width: 120 },
      { field: "floor_plan", headerName: "Floor plan", minWidth: 120, filter: true },
      { field: "gross_sq_ft", headerName: "Sq ft", width: 100 },
      { field: "has_carpet", headerName: "Carpet", width: 100 },
      { field: "has_wd_expected", headerName: "W/D exp.", width: 100 },
      { field: "is_active", headerName: "Active", width: 100 },
    ],
    [],
  );

  const rowData = useMemo(() => unitsQuery.data ?? [], [unitsQuery.data]);

  const listError = unitsQuery.isError
    ? formatAxiosMessage(unitsQuery.error)
    : null;

  return (
    <PageShell
      eyebrow="Admin"
      title="Unit Master"
      description="Import units from CSV, create individual units, and review the property unit list."
      action={<PropertySelector />}
    >
      {!propertyId ? (
        <SectionCard title="Property required">
          <p className="text-sm text-muted">Choose a property in the header to continue.</p>
        </SectionCard>
      ) : null}

      {propertyId ? (
        <>
          <SectionCard
            title="CSV import"
            description="Upload a Units.csv file. Import is all-or-nothing: any row error rolls back the entire batch."
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
              <label className="flex flex-col gap-2 text-sm font-medium text-text">
                <span className="label">File</span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  className="input max-w-md"
                  disabled={importMutation.isPending}
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setImportFile(file);
                  }}
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={strictImport}
                  disabled={importMutation.isPending}
                  onChange={(event) => setStrictImport(event.target.checked)}
                />
                Strict mode (no new units; existing codes only)
              </label>
              <button
                type="button"
                className="btn-primary"
                disabled={importMutation.isPending || !importFile}
                onClick={() => importMutation.mutate()}
              >
                {importMutation.isPending ? "Importing…" : "Run import"}
              </button>
            </div>
          </SectionCard>

          <ManualCreateUnitSection
            propertyId={propertyId}
            disabled={importMutation.isPending}
            onCreated={async () => {
              await invalidateUnits();
            }}
          />

          <SectionCard title="Units" description="All units for the selected property (optionally include inactive).">
            <label className="mb-4 flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={!activeOnly}
                onChange={(event) => setActiveOnly(!event.target.checked)}
              />
              Include inactive units
            </label>
            {listError ? (
              <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {listError}
              </p>
            ) : null}
            <div className="ag-theme-quartz-dark mt-4 h-[480px] w-full">
              <AgGridReact<UnitMasterUnitRow>
                rowData={rowData}
                columnDefs={colDefs}
                loading={unitsQuery.isLoading}
                animateRows
                defaultColDef={{ sortable: true, resizable: true, filter: true }}
                getRowId={(params) => String(params.data.unit_id)}
              />
            </div>
          </SectionCard>
        </>
      ) : null}
    </PageShell>
  );
}

function ManualCreateUnitSection({
  propertyId,
  disabled,
  onCreated,
}: {
  propertyId: number;
  disabled: boolean;
  onCreated: () => Promise<void>;
}) {
  const [unitCode, setUnitCode] = useState("");
  const [phaseId, setPhaseId] = useState<number | null>(null);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [floorPlan, setFloorPlan] = useState("");
  const [grossSqFt, setGrossSqFt] = useState("");
  const [hasCarpet, setHasCarpet] = useState(false);
  const [hasWdExpected, setHasWdExpected] = useState(false);
  const [phases, setPhases] = useState<Array<{ phase_id: number; phase_code: string; name?: string }>>([]);
  const [buildings, setBuildings] = useState<Array<{ building_id: number; building_code: string; name?: string }>>([]);

  useEffect(() => {
    api
      .get<Array<{ phase_id: number; phase_code: string; name?: string }>>(`/properties/${propertyId}/phases`)
      .then((response) => {
        setPhases(response.data);
        setPhaseId(null);
        setBuildingId(null);
      })
      .catch(() => {
        setPhases([]);
      });
  }, [propertyId]);

  useEffect(() => {
    if (!phaseId) {
      setBuildings([]);
      setBuildingId(null);
      return;
    }
    api
      .get<Array<{ building_id: number; building_code: string; name?: string }>>(`/phases/${phaseId}/buildings`)
      .then((response) => {
        setBuildings(response.data);
        setBuildingId(null);
      })
      .catch(() => {
        setBuildings([]);
      });
  }, [phaseId]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const code = unitCode.trim();
      if (!code) {
        throw new Error("Unit code is required");
      }
      const sq = grossSqFt.trim();
      let gross: number | null = null;
      if (sq !== "") {
        const n = Number(sq);
        if (Number.isNaN(n)) {
          throw new Error("Gross sq ft must be a number");
        }
        gross = n;
      }
      await api.post(`/unit-master/?property_id=${propertyId}`, {
        unit_code: code,
        phase_id: phaseId,
        building_id: buildingId,
        floor_plan: floorPlan.trim() || null,
        gross_sq_ft: gross,
        has_carpet: hasCarpet,
        has_wd_expected: hasWdExpected,
      });
    },
    onSuccess: async () => {
      toast.success("Unit created");
      setUnitCode("");
      setFloorPlan("");
      setGrossSqFt("");
      setHasCarpet(false);
      setHasWdExpected(false);
      await onCreated();
    },
    onError: (error) => {
      toast.error(formatAxiosMessage(error));
    },
  });

  return (
    <SectionCard title="Manual create" description="Add a single unit; optional phase and building placement.">
      <form
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          createMutation.mutate();
        }}
      >
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Unit code</span>
          <input
            className="input"
            value={unitCode}
            onChange={(event) => setUnitCode(event.target.value)}
            required
            disabled={disabled || createMutation.isPending}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Phase</span>
          <select
            className="input"
            value={phaseId ?? ""}
            onChange={(event) => {
              const v = event.target.value;
              setPhaseId(v === "" ? null : Number(v));
            }}
            disabled={disabled || createMutation.isPending}
          >
            <option value="">— None —</option>
            {phases.map((phase) => (
              <option key={phase.phase_id} value={phase.phase_id}>
                {phase.name ?? phase.phase_code}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Building</span>
          <select
            className="input"
            value={buildingId ?? ""}
            onChange={(event) => {
              const v = event.target.value;
              setBuildingId(v === "" ? null : Number(v));
            }}
            disabled={disabled || createMutation.isPending || !phaseId}
          >
            <option value="">— None —</option>
            {buildings.map((building) => (
              <option key={building.building_id} value={building.building_id}>
                {building.name ?? building.building_code}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Floor plan</span>
          <input
            className="input"
            value={floorPlan}
            onChange={(event) => setFloorPlan(event.target.value)}
            disabled={disabled || createMutation.isPending}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Gross sq ft</span>
          <input
            className="input"
            type="number"
            min={0}
            value={grossSqFt}
            onChange={(event) => setGrossSqFt(event.target.value)}
            disabled={disabled || createMutation.isPending}
          />
        </label>
        <div className="flex flex-col justify-end gap-3">
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={hasCarpet}
              onChange={(event) => setHasCarpet(event.target.checked)}
              disabled={disabled || createMutation.isPending}
            />
            Has carpet
          </label>
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={hasWdExpected}
              onChange={(event) => setHasWdExpected(event.target.checked)}
              disabled={disabled || createMutation.isPending}
            />
            W/D expected
          </label>
        </div>
        <div className="md:col-span-2 lg:col-span-3">
          <button
            type="submit"
            className="btn-primary"
            disabled={disabled || createMutation.isPending || !unitCode.trim()}
          >
            {createMutation.isPending ? "Creating…" : "Create unit"}
          </button>
        </div>
      </form>
    </SectionCard>
  );
}
