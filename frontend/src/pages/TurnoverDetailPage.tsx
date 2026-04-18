import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api/client";
import { addNote, resolveNote, useNotes } from "../api/useNotes";
import { useTurnover } from "../api/useTurnover";
import { useAudit } from "../api/useAudit";
import { useAuthority } from "../api/useAuthority";
import { PageShell } from "../components/PageShell";
import {
  BLOCK_OPTIONS,
  EXEC_LABELS_EXTENDED,
  EXEC_REV,
  NOTE_SEVERITIES,
  STATUS_OPTIONS,
} from "../lib/constants";
import { useDebouncedCallback } from "../lib/hooks";
import { formatDate } from "../lib/utils";

function qcLabel(tasks: Array<{ execution_status: string; manager_confirmed_at: string | null }>) {
  const completed = tasks.filter((task) => task.execution_status === "COMPLETED");
  if (completed.length === 0) {
    return "Pending";
  }

  return completed.every((task) => task.manager_confirmed_at) ? "Confirmed" : "Pending";
}

function slaLabel(level: string | undefined) {
  if (level === "BREACH") {
    return "Breach";
  }
  if (level === "WARNING") {
    return "Warning";
  }
  return "OK";
}

function sourceFromLegalToggle(checked: boolean) {
  return checked
    ? {
        legal_confirmed_at: new Date().toISOString(),
        legal_confirmation_source: "manual",
      }
    : {
        legal_confirmed_at: null,
        legal_confirmation_source: null,
      };
}

function currentStatusLabel(turnover: Record<string, unknown>) {
  const manual = String(turnover.manual_ready_status ?? "");
  if (manual === "Vacant Ready") {
    return "Vacant ready";
  }
  if (manual === "Vacant Not Ready") {
    return "Vacant not ready";
  }
  if (manual === "On Notice") {
    return "On notice";
  }

  const availability = String(turnover.availability_status ?? "").toLowerCase();
  if (availability === "vacant ready") {
    return "Vacant ready";
  }
  if (availability === "vacant not ready") {
    return "Vacant not ready";
  }
  return "On notice";
}

export function TurnoverDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [auditExpanded, setAuditExpanded] = useState(false);
  const [authorityExpanded, setAuthorityExpanded] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteSeverity, setNoteSeverity] = useState<string>(NOTE_SEVERITIES[0]);

  const turnoverId = params.turnoverId ? Number(params.turnoverId) : null;
  const turnoverQuery = useTurnover(turnoverId);
  const notesQuery = useNotes(turnoverId);
  const auditQuery = useAudit(turnoverId, auditExpanded);
  const authorityQuery = useAuthority(turnoverId, authorityExpanded);

  const detail = turnoverQuery.data;
  const turnover = detail?.turnover ?? {};
  const unit = detail?.unit ?? null;
  const tasks = detail?.tasks ?? [];
  const risks = detail?.risks ?? [];

  const invalidateDetail = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["turnover", turnoverId] }),
      queryClient.invalidateQueries({ queryKey: ["tasks", turnoverId] }),
      queryClient.invalidateQueries({ queryKey: ["notes", turnoverId] }),
      queryClient.invalidateQueries({ queryKey: ["board"] }),
    ]);
  };

  const turnoverMutation = useMutation({
    mutationFn: async ({
      field,
      value,
    }: {
      field: string;
      value: string | boolean | null;
    }) => api.patch(`/turnovers/${turnoverId}`, { field, value }),
    onSuccess: async () => {
      await invalidateDetail();
      toast.success("Saved ✓");
    },
    onError: () => {
      toast.error("Save failed");
    },
  });

  const multiFieldTurnoverMutation = useMutation({
    mutationFn: async (payload: Record<string, string | null>) => {
      const updates = Object.entries(payload).map(([field, value]) =>
        api.patch(`/turnovers/${turnoverId}`, { field, value }),
      );
      await Promise.all(updates);
    },
    onSuccess: async () => {
      await invalidateDetail();
      toast.success("Saved ✓");
    },
    onError: () => {
      toast.error("Save failed");
    },
  });

  const unitMutation = useMutation({
    mutationFn: async ({
      unitId,
      field,
      value,
    }: {
      unitId: number;
      field: string;
      value: boolean;
    }) => api.patch(`/units/${unitId}`, { field, value }),
    onSuccess: async () => {
      await invalidateDetail();
      toast.success("Saved ✓");
    },
    onError: () => {
      toast.error("Unit save failed");
    },
  });

  const taskMutation = useMutation({
    mutationFn: async ({
      taskId,
      payload,
    }: {
      taskId: number;
      payload: Record<string, string | boolean | null>;
    }) => api.patch(`/turnovers/${turnoverId}/tasks/${taskId}`, payload),
    onSuccess: async () => {
      await invalidateDetail();
      toast.success("Saved ✓");
    },
    onError: () => {
      toast.error("Task save failed");
    },
  });

  const wdMutation = useMutation({
    mutationFn: async (action: "notify" | "install" | "undo-notify" | "undo-install") => {
      if (action === "notify") {
        return api.post(`/turnovers/${turnoverId}/wd/notify`);
      }
      if (action === "install") {
        return api.post(`/turnovers/${turnoverId}/wd/install`);
      }
      if (action === "undo-notify") {
        return api.delete(`/turnovers/${turnoverId}/wd/notify`);
      }
      return api.delete(`/turnovers/${turnoverId}/wd/install`);
    },
    onSuccess: async () => {
      await invalidateDetail();
      toast.success("Saved ✓");
    },
    onError: () => {
      toast.error("W/D update failed");
    },
  });

  const addNoteMutation = useMutation({
    mutationFn: async () =>
      addNote(
        turnoverId as number,
        Number(turnover.property_id),
        noteSeverity,
        noteText.trim(),
      ),
    onSuccess: async () => {
      setNoteText("");
      await queryClient.invalidateQueries({ queryKey: ["notes", turnoverId] });
      toast.success("Note added");
    },
    onError: () => {
      toast.error("Note add failed");
    },
  });

  const resolveNoteMutation = useMutation({
    mutationFn: async (noteId: number) => resolveNote(noteId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notes", turnoverId] });
      toast.success("Note resolved");
    },
    onError: () => {
      toast.error("Note resolve failed");
    },
  });

  const handleChange = useDebouncedCallback(
    (field: string, value: string | boolean | null) => {
      turnoverMutation.mutate({ field, value });
    },
    400,
  );

  const detailTitle = useMemo(() => {
    const unitCode = typeof unit?.unit_code_norm === "string" ? unit.unit_code_norm : "Unknown Unit";
    return `Unit ${unitCode}`;
  }, [unit]);

  if (!turnoverId) {
    return (
      <PageShell title="Turnover Detail" description="Missing turnover id in URL.">
        <section className="card">
          <button
            type="button"
            onClick={() => navigate("/board")}
            className="btn-primary"
          >
            Back to Board
          </button>
        </section>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={detailTitle}
      description="Full detail and history for a single turnover."
      action={
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="btn-ghost"
        >
          Back
        </button>
      }
    >
      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Turnover #{turnoverId}</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-text-strong">
              {typeof unit?.unit_code_norm === "string" ? unit.unit_code_norm : "Unknown unit"}
            </h2>
          </div>
          <label className="inline-flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-4 py-3 text-sm font-medium text-text">
            <span>Legal confirmed</span>
            <input
              type="checkbox"
              checked={Boolean(turnover.legal_confirmed_at)}
              onChange={(event) => multiFieldTurnoverMutation.mutate(sourceFromLegalToggle(event.target.checked))}
            />
          </label>
        </div>
      </section>

      <section className="space-y-6">
        <section className="card">
          <h3 className="text-base font-semibold tracking-tight text-text-strong">Status & QC</h3>
          <div className="mt-4 grid gap-4">
            <label className="block">
              <span className="label">Status</span>
              <select
                value={currentStatusLabel(turnover)}
                onChange={(event) => handleChange("status", event.target.value)}
                className="input"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">QC</p>
              <p className="mt-2 text-base font-medium text-text-strong">{qcLabel(tasks)}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">SLA</p>
              <p className="mt-2 text-base font-medium text-text-strong">{slaLabel(detail?.sla.risk_level)}</p>
            </div>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="card">
            <h3 className="text-base font-semibold tracking-tight text-text-strong">Dates</h3>
            <div className="mt-4 grid gap-4">
              <label className="block">
                <span className="label">Move-Out</span>
                <input
                  type="date"
                  defaultValue={String(turnover.move_out_date ?? "").slice(0, 10)}
                  onChange={(event) => handleChange("move_out_date", event.target.value || null)}
                  className="input"
                />
              </label>
              <label className="block">
                <span className="label">Ready Date</span>
                <input
                  type="date"
                  defaultValue={String(turnover.report_ready_date ?? "").slice(0, 10)}
                  onChange={(event) => handleChange("report_ready_date", event.target.value || null)}
                  className="input"
                />
              </label>
              <label className="block">
                <span className="label">Move-In</span>
                <input
                  type="date"
                  defaultValue={String(turnover.move_in_date ?? "").slice(0, 10)}
                  onChange={(event) => handleChange("move_in_date", event.target.value || null)}
                  className="input"
                />
              </label>
            </div>
          </section>

          <section className="card">
            <h3 className="text-base font-semibold tracking-tight text-text-strong">W/D</h3>
            <div className="mt-4 grid gap-4">
              <label className="block">
                <span className="label">Present</span>
                <select
                  value={unit?.has_wd_expected ? "Yes" : "No"}
                  onChange={(event) =>
                    unit?.unit_id
                      ? unitMutation.mutate({
                          unitId: Number(unit.unit_id),
                          field: "has_wd_expected",
                          value: event.target.value !== "No",
                        })
                      : undefined
                  }
                  className="input"
                >
                  {WD_PRESENT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Notified</p>
                <p className="mt-2 text-sm text-text">{formatDate(String(turnover.wd_notified_at ?? ""))}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => wdMutation.mutate(turnover.wd_notified_at ? "undo-notify" : "notify")}
                    className="btn-ghost"
                  >
                    {turnover.wd_notified_at ? "Undo Notify" : "Mark Notified"}
                  </button>
                </div>
              </div>
              <div className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Installed</p>
                <p className="mt-2 text-sm text-text">{formatDate(String(turnover.wd_installed_at ?? ""))}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    disabled={!turnover.wd_notified_at && !turnover.wd_installed_at}
                    onClick={() => wdMutation.mutate(turnover.wd_installed_at ? "undo-install" : "install")}
                    className="btn-ghost"
                  >
                    {turnover.wd_installed_at ? "Undo Install" : "Mark Installed"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="card">
          <h3 className="text-base font-semibold tracking-tight text-text-strong">Risks</h3>
          <div className="mt-4 space-y-3">
            {risks.length ? (
              risks.map((risk) => (
                <div key={risk.risk_id} className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                  <p className="font-medium text-text-strong">{risk.risk_type}</p>
                  <p className="mt-1 text-sm text-muted">
                    {risk.severity} opened {formatDate(risk.opened_at)}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No active risks</p>
            )}
          </div>
        </section>
      </section>

      <section className="space-y-6">
        <section className="card">
          <h3 className="text-base font-semibold tracking-tight text-text-strong">Tasks</h3>
          <div className="mt-4 space-y-3">
            {tasks.map((task) => (
              <div key={task.task_id} className="grid gap-3 rounded-xl border border-border bg-surface-2 p-4 lg:grid-cols-[1.1fr_1fr_1fr_1fr_0.8fr_1fr]">
                <div>
                  <p className="text-sm font-semibold text-text-strong">{task.task_type}</p>
                  <p className="mt-1 text-xs text-muted">Completed {formatDate(task.completed_date)}</p>
                </div>
                <label className="block">
                  <span className="label">Execution</span>
                  <select
                    value={task.execution_status === "COMPLETED" ? "Completed" : task.execution_status === "IN_PROGRESS" ? "In Progress" : task.execution_status === "SCHEDULED" ? "Scheduled" : "Not Started"}
                    onChange={(event) =>
                      taskMutation.mutate({
                        taskId: task.task_id,
                        payload: {
                          execution_status: EXEC_REV[event.target.value] ?? "NOT_STARTED",
                        },
                      })
                    }
                    className="input"
                  >
                    {EXEC_LABELS_EXTENDED.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="label">Assignee</span>
                  <input
                    type="text"
                    defaultValue={task.assignee ?? ""}
                    onBlur={(event) =>
                      taskMutation.mutate({
                        taskId: task.task_id,
                        payload: { assignee: event.target.value || null },
                      })
                    }
                    className="input"
                  />
                </label>
                <label className="block">
                  <span className="label">Date</span>
                  <input
                    type="date"
                    defaultValue={String(task.vendor_due_date ?? "").slice(0, 10)}
                    onChange={(event) =>
                      taskMutation.mutate({
                        taskId: task.task_id,
                        payload: { vendor_due_date: event.target.value || null },
                      })
                    }
                    className="input"
                  />
                </label>
                <label className="block">
                  <span className="label">Required</span>
                  <input
                    type="checkbox"
                    checked={task.required}
                    onChange={(event) =>
                      taskMutation.mutate({
                        taskId: task.task_id,
                        payload: { required: event.target.checked },
                      })
                    }
                  />
                </label>
                <label className="block">
                  <span className="label">Blocking</span>
                  <select
                    value={task.blocking ? "—" : "Not Blocking"}
                    onChange={(event) =>
                      taskMutation.mutate({
                        taskId: task.task_id,
                        payload: { blocking: event.target.value !== "Not Blocking" },
                      })
                    }
                    className="input"
                  >
                    {BLOCK_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <h3 className="text-base font-semibold tracking-tight text-text-strong">Notes</h3>
          <div className="mt-4 space-y-3">
            {(notesQuery.data ?? []).map((note: Record<string, unknown>) => (
              <div key={String(note.note_id)} className="flex items-start justify-between gap-4 rounded-xl border border-border bg-surface-2 px-4 py-3">
                <div>
                  <p className="font-medium text-text-strong">{String(note.text ?? "")}</p>
                  <p className="mt-1 text-sm text-muted">
                    {String(note.severity ?? "INFO")}
                  </p>
                </div>
                {!note.resolved_at ? (
                  <button
                    type="button"
                    onClick={() => resolveNoteMutation.mutate(Number(note.note_id))}
                    className="btn-ghost"
                  >
                    Resolve
                  </button>
                ) : (
                  <span className="text-sm text-muted">Resolved</span>
                )}
              </div>
            ))}
          </div>

          <div className="mt-4 grid gap-3">
            <textarea
              value={noteText}
              onChange={(event) => setNoteText(event.target.value)}
              placeholder="Add note"
              className="input min-h-28"
            />
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={noteSeverity}
                onChange={(event) => setNoteSeverity(event.target.value)}
                className="input w-auto"
              >
                {NOTE_SEVERITIES.map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={!noteText.trim() || !turnover.property_id}
                onClick={() => addNoteMutation.mutate()}
                className="btn-primary"
              >
                Add Note
              </button>
            </div>
          </div>
        </section>
      </section>

      <section className="space-y-6">
        <details
          className="card"
          onToggle={(event) => setAuthorityExpanded((event.currentTarget as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer text-base font-semibold tracking-tight text-text-strong">Authority</summary>
          <div className="mt-4">
            {authorityQuery.data?.rows?.map((row) => (
              <div key={row.field} className="grid grid-cols-[1fr_1fr_0.8fr] gap-3 border-b border-border py-2 text-sm last:border-b-0">
                <span className="font-medium text-text-strong">{row.field}</span>
                <span className="text-text">{row.current_value}</span>
                <span className="text-muted">{row.source}</span>
              </div>
            ))}
          </div>
        </details>

        <details
          className="card"
          onToggle={(event) => setAuditExpanded((event.currentTarget as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer text-base font-semibold tracking-tight text-text-strong">Audit History</summary>
          <div className="mt-4 space-y-3">
            {(auditQuery.data ?? []).map((entry) => (
              <div key={`${entry.changed_at}-${entry.field_name}-${entry.new_value}`} className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm">
                <p className="font-medium text-text-strong">
                  {entry.field_name}: {entry.old_value ?? "—"} → {entry.new_value ?? "—"}
                </p>
                <p className="mt-1 text-muted">
                  {formatDate(entry.changed_at)} by {entry.actor ?? "system"} via {entry.source ?? "—"}
                </p>
              </div>
            ))}
          </div>
        </details>
      </section>
    </PageShell>
  );
}
const WD_PRESENT_OPTIONS = ["No", "Yes"] as const;
