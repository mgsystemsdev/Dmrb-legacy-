import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../api/client";
import { useBoard } from "../api/useBoard";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";
import { EXEC_LABELS, EXEC_REV, TASK_DISPLAY } from "../lib/constants";
import { formatDate } from "../lib/utils";

type ScheduleRow = {
  taskId: number;
  turnoverId: number;
  unitCode: string;
  taskType: string;
  assignee: string;
  scheduledDate: string;
  vendorDueDate: string;
  executionStatus: string;
};

type PendingEdit = Partial<Pick<ScheduleRow, "assignee" | "scheduledDate" | "vendorDueDate" | "executionStatus">>;

export function OperationsSchedulePage() {
  const queryClient = useQueryClient();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const boardQuery = useBoard(propertyId);
  const [roleView, setRoleView] = useState<"manager" | "vendor">("manager");
  const [pending, setPending] = useState<Record<number, PendingEdit>>({});

  const rows = useMemo<ScheduleRow[]>(() => {
    return (boardQuery.data?.rows ?? []).flatMap((row) =>
      row.tasks.map((task) => ({
        taskId: task.task_id,
        turnoverId: row.turnover_id,
        unitCode: row.unit_code,
        taskType: task.task_type,
        assignee: task.assignee ?? "",
        scheduledDate: task.scheduled_date ?? "",
        vendorDueDate: task.vendor_due_date ?? "",
        executionStatus: task.execution_status,
      })),
    );
  }, [boardQuery.data?.rows]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const updates = Object.entries(pending).map(([taskId, changes]) => {
        const base = rows.find((row) => row.taskId === Number(taskId));
        if (!base) {
          return Promise.resolve();
        }
        return api.patch(`/turnovers/${base.turnoverId}/tasks/${base.taskId}`, {
          assignee: (changes.assignee ?? base.assignee) || null,
          scheduled_date: (changes.scheduledDate ?? base.scheduledDate) || null,
          vendor_due_date: (changes.vendorDueDate ?? base.vendorDueDate) || null,
          execution_status:
            EXEC_REV[
              changes.executionStatus ??
                (EXEC_LABELS.find((label) => EXEC_REV[label] === base.executionStatus) ?? "Not Started")
            ] ?? base.executionStatus,
        });
      });
      await Promise.all(updates);
    },
    onSuccess: async () => {
      setPending({});
      await queryClient.invalidateQueries({ queryKey: ["board", propertyId] });
      toast.success("Schedule saved");
    },
    onError: () => {
      toast.error("Batch save failed");
    },
  });

  const displayRows = useMemo(() => {
    if (roleView === "vendor") {
      return rows.filter((row) => row.assignee.trim());
    }
    return rows;
  }, [roleView, rows]);

  const updateRow = (taskId: number, field: keyof PendingEdit, value: string) => {
    setPending((current) => ({
      ...current,
      [taskId]: {
        ...current[taskId],
        [field]: value,
      },
    }));
  };

  return (
    <PageShell
      title="Operations Schedule"
      description="Daily work schedule for managers and vendors."
      action={<PropertySelector />}
    >
      <SectionCard
        title="Schedule View"
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <div className="tab-group">
              <button
                type="button"
                onClick={() => setRoleView("manager")}
                className={`tab-item ${roleView === "manager" ? "tab-item-active" : ""}`}
              >
                Manager
              </button>
              <button
                type="button"
                onClick={() => setRoleView("vendor")}
                className={`tab-item ${roleView === "vendor" ? "tab-item-active" : ""}`}
              >
                Vendor
              </button>
            </div>
            {roleView === "manager" ? (
              <button
                type="button"
                onClick={() => saveMutation.mutate()}
                disabled={!Object.keys(pending).length || saveMutation.isPending}
                className="btn-primary"
              >
                {saveMutation.isPending ? "Saving..." : "Batch Save"}
              </button>
            ) : null}
          </div>
        }
      >
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-2 text-left text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Unit</th>
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Assignee</th>
                <th className="px-4 py-3 font-medium">Scheduled</th>
                <th className="px-4 py-3 font-medium">Vendor Due</th>
                <th className="px-4 py-3 font-medium">Execution</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row) => {
                const patch = pending[row.taskId] ?? {};
                const executionLabel = EXEC_LABELS.find((label) => EXEC_REV[label] === row.executionStatus) ?? "Not Started";
                return (
                  <tr key={row.taskId} className="border-t border-border">
                    <td className="px-4 py-3 font-medium text-text-strong">{row.unitCode}</td>
                    <td className="px-4 py-3 text-text">{TASK_DISPLAY[row.taskType] ?? row.taskType}</td>
                    <td className="px-4 py-3 text-text">
                      {roleView === "manager" ? (
                        <input
                          value={patch.assignee ?? row.assignee}
                          onChange={(event) => updateRow(row.taskId, "assignee", event.target.value)}
                          className="input"
                        />
                      ) : (
                        (patch.assignee ?? row.assignee) || "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-text">
                      {roleView === "manager" ? (
                        <input
                          type="date"
                          value={patch.scheduledDate ?? row.scheduledDate}
                          onChange={(event) => updateRow(row.taskId, "scheduledDate", event.target.value)}
                          className="input"
                        />
                      ) : (
                        formatDate(patch.scheduledDate ?? row.scheduledDate)
                      )}
                    </td>
                    <td className="px-4 py-3 text-text">
                      {roleView === "manager" ? (
                        <input
                          type="date"
                          value={patch.vendorDueDate ?? row.vendorDueDate}
                          onChange={(event) => updateRow(row.taskId, "vendorDueDate", event.target.value)}
                          className="input"
                        />
                      ) : (
                        formatDate(patch.vendorDueDate ?? row.vendorDueDate)
                      )}
                    </td>
                    <td className="px-4 py-3 text-text">
                      {roleView === "manager" ? (
                        <select
                          value={patch.executionStatus ?? executionLabel}
                          onChange={(event) => updateRow(row.taskId, "executionStatus", event.target.value)}
                          className="input"
                        >
                          {EXEC_LABELS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      ) : (
                        patch.executionStatus ?? executionLabel
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </PageShell>
  );
}
