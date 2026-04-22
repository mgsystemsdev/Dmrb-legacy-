import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import axios from "axios";
import { toast } from "sonner";
import { api } from "../api/client";
import { useScopedPropertyPhases } from "../api/usePhaseScope";
import {
  useCreateUnit,
  useImportUnits,
  useUnits,
  type UnitRow,
} from "../api/useUnitMaster";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";

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

type UnitsGridRow = UnitRow & {
  unit_id: number;
  unit_code?: string | null;
  phase_name?: string | null;
  building_name?: string | null;
  created_at?: string | null;
};

/** Last import outcome from a successful /api/unit-master/import (200) or from error body (4xx) for display. */
type UnitMasterImportResultDisplay = {
  created: number;
  skipped: number;
  errors: string[];
};

function importErrorsFromAxiosData(
  data: unknown,
): string[] {
  if (!data || typeof data !== "object") {
    return [];
  }
  const errors = (data as { errors?: unknown }).errors;
  if (!Array.isArray(errors)) {
    return [];
  }
  return errors.filter((e): e is string => typeof e === "string" && e.length > 0);
}

function formatCellDash(params: ValueFormatterParams): string {
  const v = params.value;
  if (v == null || v === "") {
    return "—";
  }
  return String(v);
}

function formatCreatedAt(params: ValueFormatterParams): string {
  const v = params.value as string | null | undefined;
  if (!v) {
    return "—";
  }
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) {
    return String(v);
  }
  return d.toLocaleString();
}

export function UnitMasterPage() {
  const propertyId = usePropertyStore((state) => state.propertyId);
  const [activeOnly, setActiveOnly] = useState(true);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [strictImport, setStrictImport] = useState(false);
  const [quickSearch, setQuickSearch] = useState("");
  const [importResult, setImportResult] = useState<UnitMasterImportResultDisplay | null>(null);

  const unitsQuery = useUnits(propertyId, { activeOnly });
  const importMutation = useImportUnits();

  useEffect(() => {
    setImportResult(null);
  }, [propertyId]);

  const colDefs = useMemo<ColDef<UnitsGridRow>[]>(
    () => [
      {
        field: "unit_code",
        headerName: "Unit code",
        minWidth: 120,
        flex: 1,
        filter: "agTextColumnFilter",
        valueFormatter: formatCellDash,
      },
      {
        field: "phase_name",
        headerName: "Phase",
        minWidth: 140,
        flex: 1,
        filter: "agTextColumnFilter",
        valueFormatter: formatCellDash,
      },
      {
        field: "building_name",
        headerName: "Building",
        minWidth: 140,
        flex: 1,
        filter: "agTextColumnFilter",
        valueFormatter: formatCellDash,
      },
      {
        field: "created_at",
        headerName: "Created at",
        minWidth: 180,
        flex: 1,
        filter: "agTextColumnFilter",
        valueFormatter: formatCreatedAt,
      },
    ],
    [],
  );

  const defaultColDef = useMemo<ColDef<UnitsGridRow>>(
    () => ({
      sortable: true,
      resizable: true,
      filter: "agTextColumnFilter",
      floatingFilter: true,
      suppressHeaderMenuButton: false,
    }),
    [],
  );

  const rowData = useMemo(() => (unitsQuery.data ?? []) as UnitsGridRow[], [unitsQuery.data]);

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
                disabled={importMutation.isPending || !importFile || !propertyId}
                onClick={() => {
                  if (!propertyId || !importFile) {
                    return;
                  }
                  setImportResult(null);
                  importMutation.mutate(
                    { propertyId, file: importFile, strict: strictImport },
                    {
                      onSuccess: (data) => {
                        if (!data.success) {
                          toast.error(data.errors?.join("; ") || "Import failed");
                          return;
                        }
                        const d = data.data;
                        if (!d) {
                          toast.error("Import returned no data");
                          return;
                        }
                        const rowErrors = Array.isArray(d.errors) ? d.errors : [];
                        setImportResult({
                          created: d.created,
                          skipped: d.skipped,
                          errors: rowErrors,
                        });
                        if (rowErrors.length > 0) {
                          toast("Import finished — see row details below", {
                            description: `${d.created} created, ${d.skipped} skipped, ${rowErrors.length} message(s)`,
                          });
                        } else {
                          toast.success(
                            `Import complete — ${d.created} created, ${d.skipped} skipped`,
                          );
                        }
                        setImportFile(null);
                      },
                      onError: (error) => {
                        const msg = formatAxiosMessage(error);
                        toast.error(msg);
                        if (axios.isAxiosError(error) && error.response?.data) {
                          const rowErrors = importErrorsFromAxiosData(error.response.data);
                          if (rowErrors.length) {
                            setImportResult({ created: 0, skipped: 0, errors: rowErrors });
                          }
                        }
                      },
                    },
                  );
                }}
              >
                {importMutation.isPending ? "Importing…" : "Run import"}
              </button>
            </div>

            {importResult ? (
              <div
                className="mt-4 rounded-md border border-border bg-surface-2/40 p-4"
                role="status"
                aria-live="polite"
              >
                <p className="text-sm font-medium text-text">Last import</p>
                <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-text">
                  <div className="flex gap-1.5">
                    <dt className="text-muted">Created</dt>
                    <dd className="font-medium tabular-nums">{importResult.created}</dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="text-muted">Skipped</dt>
                    <dd className="font-medium tabular-nums">{importResult.skipped}</dd>
                  </div>
                  <div className="flex gap-1.5">
                    <dt className="text-muted">Errors</dt>
                    <dd className="font-medium tabular-nums">{importResult.errors.length}</dd>
                  </div>
                </dl>
                {importResult.errors.length > 0 ? (
                  <div className="mt-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted">
                      Row and validation messages
                    </p>
                    <ul
                      className="mt-2 max-h-48 list-none space-y-1.5 overflow-y-auto overscroll-y-contain rounded border border-border/80 bg-surface-1/40 py-2 pl-2 pr-2 text-sm text-text"
                      role="list"
                    >
                      {importResult.errors.map((err, i) => (
                        <li key={`${i}-${err.slice(0, 32)}`} className="break-words border-b border-border/30 pb-1.5 last:border-b-0 last:pb-0">
                          {err}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}
          </SectionCard>

          <ManualCreateUnitSection propertyId={propertyId} disabled={importMutation.isPending} />

          <SectionCard title="Units" description="All units for the selected property (optionally include inactive).">
            <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <label className="flex items-center gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={!activeOnly}
                  onChange={(event) => setActiveOnly(!event.target.checked)}
                />
                Include inactive units
              </label>
              <label className="flex min-w-[240px] flex-1 flex-col gap-1 text-sm font-medium text-text sm:max-w-md">
                <span className="label">Quick search</span>
                <input
                  type="search"
                  className="input"
                  placeholder="Filter rows…"
                  value={quickSearch}
                  onChange={(event) => setQuickSearch(event.target.value)}
                  autoComplete="off"
                />
              </label>
            </div>
            {listError ? (
              <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {listError}
              </p>
            ) : null}
            <div className="ag-theme-quartz-dark mt-4 h-[520px] w-full">
              <AgGridReact<UnitsGridRow>
                rowData={rowData}
                columnDefs={colDefs}
                defaultColDef={defaultColDef}
                loading={unitsQuery.isLoading}
                animateRows
                quickFilterText={quickSearch}
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
}: {
  propertyId: number;
  disabled: boolean;
}) {
  const [unitCode, setUnitCode] = useState("");
  const [phaseId, setPhaseId] = useState<number | null>(null);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [floorPlan, setFloorPlan] = useState("");
  const [grossSqFt, setGrossSqFt] = useState("");
  const [hasCarpet, setHasCarpet] = useState(false);
  const [hasWdExpected, setHasWdExpected] = useState(false);
  const { filteredPhases, isPending: phasesScopePending } = useScopedPropertyPhases(propertyId);
  const [buildings, setBuildings] = useState<Array<{ building_id: number; building_code: string; name?: string }>>([]);

  useEffect(() => {
    setPhaseId(null);
    setBuildingId(null);
  }, [propertyId]);

  useEffect(() => {
    if (filteredPhases == null) {
      return;
    }
    if (filteredPhases.length === 0) {
      setPhaseId(null);
      setBuildingId(null);
      return;
    }
    if (phaseId != null && !filteredPhases.some((p) => p.phase_id === phaseId)) {
      setPhaseId(null);
      setBuildingId(null);
    }
  }, [propertyId, filteredPhases, phaseId]);

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

  const createUnit = useCreateUnit();

  return (
    <SectionCard title="Manual create" description="Add a single unit; optional phase and building placement.">
      <form
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          const code = unitCode.trim();
          if (!code) {
            toast.error("Unit code is required");
            return;
          }
          const sq = grossSqFt.trim();
          let gross: number | null = null;
          if (sq !== "") {
            const n = Number(sq);
            if (Number.isNaN(n)) {
              toast.error("Gross sq ft must be a number");
              return;
            }
            gross = n;
          }
          createUnit.mutate(
            {
              propertyId,
              body: {
                unit_code: code,
                phase_id: phaseId,
                building_id: buildingId,
                floor_plan: floorPlan.trim() || null,
                gross_sq_ft: gross,
                has_carpet: hasCarpet,
                has_wd_expected: hasWdExpected,
              },
            },
            {
              onSuccess: () => {
                toast.success("Unit created");
                setUnitCode("");
                setFloorPlan("");
                setGrossSqFt("");
                setHasCarpet(false);
                setHasWdExpected(false);
              },
              onError: (error) => {
                toast.error(formatAxiosMessage(error));
              },
            },
          );
        }}
      >
        <label className="flex flex-col gap-2 text-sm font-medium text-text">
          <span className="label">Unit code</span>
          <input
            className="input"
            value={unitCode}
            onChange={(event) => setUnitCode(event.target.value)}
            required
            disabled={disabled || createUnit.isPending}
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
            disabled={disabled || createUnit.isPending || phasesScopePending}
          >
            <option value="">— None —</option>
            {phasesScopePending && phaseId != null ? (
              <option value={phaseId}>
                {filteredPhases?.find((p) => p.phase_id === phaseId)?.name ??
                  filteredPhases?.find((p) => p.phase_id === phaseId)?.phase_code ??
                  "…"}
              </option>
            ) : null}
            {!phasesScopePending && filteredPhases
              ? filteredPhases.map((p) => (
                  <option key={p.phase_id} value={p.phase_id}>
                    {p.name ?? p.phase_code}
                  </option>
                ))
              : null}
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
            disabled={disabled || createUnit.isPending || !phaseId}
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
            disabled={disabled || createUnit.isPending}
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
            disabled={disabled || createUnit.isPending}
          />
        </label>
        <div className="flex flex-col justify-end gap-3">
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={hasCarpet}
              onChange={(event) => setHasCarpet(event.target.checked)}
              disabled={disabled || createUnit.isPending}
            />
            Has carpet
          </label>
          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={hasWdExpected}
              onChange={(event) => setHasWdExpected(event.target.checked)}
              disabled={disabled || createUnit.isPending}
            />
            W/D expected
          </label>
        </div>
        <div className="md:col-span-2 lg:col-span-3">
          <button
            type="submit"
            className="btn-primary"
            disabled={disabled || createUnit.isPending || !unitCode.trim()}
          >
            {createUnit.isPending ? "Creating…" : "Create unit"}
          </button>
        </div>
      </form>
    </SectionCard>
  );
}
