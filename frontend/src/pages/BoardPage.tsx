import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  CellValueChangedEvent,
  ColDef,
  ValueFormatterParams,
} from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api/client";
import { useScopedPropertyPhases } from "../api/usePhaseScope";
import { useBoard, type BoardRow } from "../api/useBoard";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { StatusBadge } from "../components/StatusBadge";
import {
  EXEC_LABELS,
  EXEC_MAP,
  EXEC_REV,
  STATUS_OPTIONS,
  TASK_COLS,
} from "../lib/constants";
import { formatDate, formatTaskCompletion } from "../lib/utils";
import { usePropertyStore } from "../stores/useProperty";

type BoardFilterState = {
  search?: string;
  phase?: string;
  nvm?: string;
  status?: string;
  qc?: string;
  board_filter?: string;
};

type TabKey = "info" | "tasks";
type TaskGridValue = string | number | [number, number] | null | undefined;
type TaskMutationPayload = {
  vendor_due_date?: string | null;
  execution_status?: string | null;
};

type TaskGridRow = {
  turnover_id: number;
  unit_code: string;
  status: string;
  task_completion: [number, number];
} & Record<string, TaskGridValue>;

const NVM_OPTIONS = ["All", "Notice", "Notice + SMI", "Vacant", "Move-In"] as const;
const QC_OPTIONS = ["All", "Pending", "Confirmed"] as const;

function getTaskColumnOrder(taskTypes: string[]) {
  const ordered = TASK_COLS.filter((taskType) => taskTypes.includes(taskType));
  const extras = taskTypes.filter((taskType) => !ordered.includes(taskType as (typeof TASK_COLS)[number]));
  return [...ordered, ...extras];
}

function dateValueFormatter(params: ValueFormatterParams) {
  return formatDate(params.value as string | null | undefined);
}

function serializeDateInput(value: unknown): string | null {
  if (!value) {
    return null;
  }

  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }

  const asString = String(value).trim();
  if (!asString) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(asString)) {
    return asString;
  }

  const parsed = new Date(asString);
  if (Number.isNaN(parsed.getTime())) {
    return asString;
  }

  return parsed.toISOString().slice(0, 10);
}

export function BoardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const { filteredPhases, isPending: phasesScopePending } = useScopedPropertyPhases(propertyId);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabKey>("info");

  const filters = useMemo<BoardFilterState>(
    () => ({
      search: searchParams.get("search") ?? undefined,
      phase: searchParams.get("phase") ?? undefined,
      nvm: searchParams.get("nvm") ?? undefined,
      status: searchParams.get("status") ?? undefined,
      qc: searchParams.get("qc") ?? undefined,
      board_filter: searchParams.get("board_filter") ?? undefined,
    }),
    [searchParams],
  );

  // Keep `phase` query param aligned with scope: must be a phase_code, or removed (= All).
  useEffect(() => {
    if (propertyId == null || propertyId < 1) {
      return;
    }
    if (filteredPhases == null) {
      return;
    }
    const param = searchParams.get("phase");
    if (!param) {
      return;
    }
    if (filteredPhases.length === 0) {
      const next = new URLSearchParams(searchParams);
      next.delete("phase");
      setSearchParams(next, { replace: true });
      return;
    }
    if (filteredPhases.some((p) => p.phase_code === param)) {
      return;
    }
    const byName = filteredPhases.find((p) => (p.name?.trim() ? p.name.trim() : "") === param);
    if (byName) {
      const next = new URLSearchParams(searchParams);
      next.set("phase", byName.phase_code);
      setSearchParams(next, { replace: true });
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("phase");
    setSearchParams(next, { replace: true });
  }, [propertyId, filteredPhases, searchParams, setSearchParams]);

  const { data, isLoading } = useBoard(propertyId, filters);

  const invalidateBoard = () =>
    queryClient.invalidateQueries({
      queryKey: ["board", propertyId],
    });

  const turnoverMutation = useMutation({
    mutationFn: async ({
      id,
      field,
      value,
    }: {
      id: number;
      field: string;
      value: string | null;
    }) => api.patch(`/turnovers/${id}`, { field, value }),
    onSuccess: async () => {
      await invalidateBoard();
      toast.success("Board updated");
    },
    onError: () => {
      toast.error("Turnover update failed");
    },
  });

  const taskMutation = useMutation({
    mutationFn: async ({
      turnoverId,
      taskId,
      payload,
    }: {
      turnoverId: number;
      taskId: number;
      payload: TaskMutationPayload;
    }) => api.patch(`/turnovers/${turnoverId}/tasks/${taskId}`, payload),
    onSuccess: async () => {
      await invalidateBoard();
      toast.success("Task updated");
    },
    onError: () => {
      toast.error("Task update failed");
    },
  });

  const updateFilter = (key: keyof BoardFilterState, value: string) => {
    const next = new URLSearchParams(searchParams);

    if (!value || value === "All") {
      next.delete(key);
    } else {
      next.set(key, value);
    }

    setSearchParams(next, { replace: true });
  };

  const infoColDefs = useMemo<ColDef<BoardRow>[]>(
    () => [
      { field: "unit_code", headerName: "Unit", width: 90 },
      {
        field: "status",
        headerName: "Status",
        editable: true,
        width: 150,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: [...STATUS_OPTIONS] },
      },
      {
        field: "move_out_date",
        headerName: "Move-Out",
        editable: true,
        width: 130,
        cellEditor: "agDateStringCellEditor",
        valueFormatter: dateValueFormatter,
      },
      {
        field: "report_ready_date",
        headerName: "Ready Date",
        editable: true,
        width: 130,
        cellEditor: "agDateStringCellEditor",
        valueFormatter: dateValueFormatter,
      },
      {
        field: "move_in_date",
        headerName: "Move-In",
        editable: true,
        width: 130,
        cellEditor: "agDateStringCellEditor",
        valueFormatter: dateValueFormatter,
      },
      {
        field: "phase",
        headerName: "Phase",
        minWidth: 150,
      },
      {
        field: "nvm",
        headerName: "N/V/M",
        width: 120,
      },
      {
        field: "qc",
        headerName: "QC",
        width: 120,
        editable: true,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: QC_OPTIONS.filter((option) => option !== "All") },
      },
      {
        field: "readiness",
        headerName: "Readiness",
        minWidth: 150,
        cellRenderer: ({ value }: { value: string }) => (
          <StatusBadge label={value} toneKey={value} />
        ),
      },
      {
        field: "priority",
        headerName: "Priority",
        minWidth: 150,
      },
      {
        field: "days_since_move_out",
        headerName: "DV",
        width: 90,
      },
      {
        field: "days_to_be_ready",
        headerName: "DTBR",
        width: 90,
      },
      {
        field: "task_completion",
        headerName: "Tasks",
        width: 100,
        valueFormatter: ({ value }) => formatTaskCompletion(value as [number, number]),
      },
      {
        field: "alert",
        headerName: "Alert",
        minWidth: 180,
      },
      {
        field: "notes_summary",
        headerName: "Notes",
        minWidth: 220,
      },
    ],
    [],
  );

  const taskRowData = useMemo<TaskGridRow[]>(() => {
    if (!data) {
      return [];
    }

    const orderedTaskTypes = getTaskColumnOrder(data.task_types_present);

    return data.rows.map((row) => {
      const taskMap = Object.fromEntries(row.tasks.map((task) => [task.task_type, task]));
      const base: TaskGridRow = {
        turnover_id: row.turnover_id,
        unit_code: row.unit_code,
        status: row.status,
        task_completion: row.task_completion,
      };

      for (const taskType of orderedTaskTypes) {
        const task = taskMap[taskType];
        base[taskType] = task ? EXEC_MAP[task.execution_status] ?? task.execution_status : "—";
        base[`${taskType}_date`] = task?.vendor_due_date ?? null;
      }

      return base;
    });
  }, [data]);

  const taskColDefs = useMemo<ColDef<TaskGridRow>[]>(() => {
    const orderedTaskTypes = getTaskColumnOrder(data?.task_types_present ?? []);
    const cols: ColDef<TaskGridRow>[] = [
      { field: "unit_code", headerName: "Unit", width: 90 },
      { field: "status", headerName: "Status", width: 150 },
      {
        field: "task_completion",
        headerName: "Tasks",
        width: 100,
        valueFormatter: ({ value }) => formatTaskCompletion(value as [number, number]),
      },
    ];

    for (const taskType of orderedTaskTypes) {
      cols.push({
        field: taskType,
        headerName: taskType,
        editable: true,
        minWidth: 150,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: [...EXEC_LABELS, "—"] },
      });
      cols.push({
        field: `${taskType}_date`,
        headerName: `${taskType} Date`,
        editable: true,
        minWidth: 150,
        cellEditor: "agDateStringCellEditor",
        valueFormatter: dateValueFormatter,
      });
    }

    return cols;
  }, [data]);

  const onTurnoverCellValueChanged = (event: CellValueChangedEvent<BoardRow>) => {
    if (!event.data || event.newValue === event.oldValue) {
      return;
    }

    const editableFields = new Set(["status", "move_out_date", "report_ready_date", "move_in_date", "qc"]);
    if (!event.colDef.field || !editableFields.has(event.colDef.field)) {
      return;
    }

    if (event.colDef.field === "qc") {
      const qcTask = event.data.tasks.find((task) => task.task_type === "QUALITY_CONTROL");
      if (!qcTask) {
        toast.error("No QUALITY_CONTROL task exists for this row");
        return;
      }

      taskMutation.mutate({
        turnoverId: event.data.turnover_id,
        taskId: qcTask.task_id,
        payload: {
          execution_status: event.newValue === "Confirmed" ? "COMPLETED" : "NOT_STARTED",
        },
      });
      return;
    }

    turnoverMutation.mutate({
      id: event.data.turnover_id,
      field: event.colDef.field,
      value: event.colDef.field.includes("date")
        ? serializeDateInput(event.newValue)
        : event.newValue
          ? String(event.newValue)
          : null,
    });
  };

  const onTaskCellValueChanged = (event: CellValueChangedEvent<TaskGridRow>) => {
    if (!event.data || event.newValue === event.oldValue || !data || !event.colDef.field) {
      return;
    }

    const row = data.rows.find((boardRow) => boardRow.turnover_id === event.data?.turnover_id);
    if (!row) {
      return;
    }

    const field = event.colDef.field;
    const isDateField = field.endsWith("_date");
    const taskType = isDateField ? field.replace(/_date$/, "") : field;
    const task = row.tasks.find((item) => item.task_type === taskType);

    if (!task) {
      return;
    }

    const payload = isDateField
      ? { vendor_due_date: serializeDateInput(event.newValue) }
      : {
          execution_status:
            event.newValue === "—" || event.newValue == null
              ? "NOT_STARTED"
              : EXEC_REV[String(event.newValue)] ?? String(event.newValue),
        };

    taskMutation.mutate({
      turnoverId: row.turnover_id,
      taskId: task.task_id,
      payload,
    });
  };

  const onBoardRowClicked = (turnoverId?: number) => {
    if (!turnoverId) {
      return;
    }
    navigate(`/unit/${turnoverId}`);
  };

  const onTaskRowClicked = (turnoverId?: number) => {
    if (!turnoverId) {
      return;
    }
    navigate(`/unit/${turnoverId}`);
  };

  const phaseOptions = useMemo((): { value: string; label: string }[] => {
    if (filteredPhases == null) {
      return [];
    }
    if (filteredPhases.length === 0) {
      return [];
    }
    return [...filteredPhases]
      .map((p) => ({
        value: p.phase_code,
        label: p.name && p.name.trim() ? p.name.trim() : p.phase_code,
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [filteredPhases]);

  return (
    <PageShell
      title="Board"
      description="Track and update every open turnover across your portfolio."
      action={<PropertySelector />}
    >
      <section className="card">
        <div className="grid gap-3 md:grid-cols-5">
          <label className="block">
            <span className="label">Search</span>
            <input
              value={filters.search ?? ""}
              onChange={(event) => updateFilter("search", event.target.value)}
              placeholder="Unit code"
              className="input"
            />
          </label>
          <label className="block">
            <span className="label">Phase</span>
            <select
              value={filters.phase ?? "All"}
              onChange={(event) => updateFilter("phase", event.target.value)}
              className="input"
              disabled={phasesScopePending || (filteredPhases != null && filteredPhases.length === 0)}
            >
              <option value="All">All</option>
              {phasesScopePending && filters.phase ? (
                <option value={filters.phase}>{filters.phase}</option>
              ) : null}
              {!phasesScopePending
                ? phaseOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))
                : null}
            </select>
          </label>
          <label className="block">
            <span className="label">N/V/M</span>
            <select
              value={filters.nvm ?? "All"}
              onChange={(event) => updateFilter("nvm", event.target.value)}
              className="input"
            >
              {NVM_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Status</span>
            <select
              value={filters.status ?? "All"}
              onChange={(event) => updateFilter("status", event.target.value)}
              className="input"
            >
              <option value="All">All</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">QC</span>
            <select
              value={filters.qc ?? "All"}
              onChange={(event) => updateFilter("qc", event.target.value)}
              className="input"
            >
              {QC_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="card">
        <div className="mb-4 flex items-center justify-between">
          <div className="tab-group">
            <button
              type="button"
              onClick={() => setActiveTab("info")}
              className={`tab-item ${activeTab === "info" ? "tab-item-active" : ""}`}
            >
              Unit Info
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("tasks")}
              className={`tab-item ${activeTab === "tasks" ? "tab-item-active" : ""}`}
            >
              Unit Tasks
            </button>
          </div>
          <p className="text-sm text-muted">{data?.total ?? 0} rows</p>
        </div>

        {activeTab === "info" ? (
          <div className="ag-theme-quartz-dark h-[620px] w-full">
            <AgGridReact<BoardRow>
              rowData={data?.rows ?? []}
              columnDefs={infoColDefs}
              loading={isLoading}
              animateRows
              singleClickEdit
              getRowId={(params) => params.data.turnover_id.toString()}
              onCellValueChanged={onTurnoverCellValueChanged}
              onRowClicked={(event) => onBoardRowClicked(event.data?.turnover_id)}
            />
          </div>
        ) : (
          <div className="ag-theme-quartz-dark h-[620px] w-full">
            <AgGridReact<TaskGridRow>
              rowData={taskRowData}
              columnDefs={taskColDefs}
              loading={isLoading}
              animateRows
              singleClickEdit
              getRowId={(params) => params.data.turnover_id.toString()}
              onCellValueChanged={onTaskCellValueChanged}
              onRowClicked={(event) => onTaskRowClicked(event.data?.turnover_id)}
            />
          </div>
        )}
      </section>
    </PageShell>
  );
}
