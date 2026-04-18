import { Link } from "react-router-dom";
import { PageShell } from "../components/PageShell";
import { MetricGrid } from "../components/MetricGrid";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { useWorkflowSummary } from "../api/useOperations";
import { usePropertyStore } from "../stores/useProperty";
import { formatDate } from "../lib/utils";

const REPORT_LABELS: Record<string, string> = {
  MOVE_OUTS: "Move-Out",
  PENDING_MOVE_INS: "Move-In",
  AVAILABLE_UNITS: "Available",
  PENDING_FAS: "FAS",
};

export function MorningWorkflowPage() {
  const propertyId = usePropertyStore((state) => state.propertyId);
  const workflowQuery = useWorkflowSummary(propertyId);
  const workflow = workflowQuery.data;

  return (
    <PageShell
      title="Morning Workflow"
      description="Start-of-day snapshot of what needs attention across your properties."
      action={<PropertySelector />}
    >
      <MetricGrid
        metrics={[
          { label: "Active Units", value: workflow?.metrics.active ?? "—" },
          { label: "Violations", value: workflow?.metrics.violations ?? "—", tone: "danger" },
          { label: "Work Stalled", value: workflow?.metrics.work_stalled ?? "—", tone: "warning" },
          { label: "Move-In Risk", value: workflow?.metrics.move_in_risk ?? "—", tone: "danger" },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Import Status" description="Confirm the source reports are fresh before the rest of the day starts.">
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(REPORT_LABELS).map(([key, label]) => {
              const timestamp = workflow?.import_timestamps[key] ?? null;
              return (
                <div key={key} className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                  <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted">{label}</p>
                  <p className="mt-2 text-sm font-medium text-text-strong">
                    {timestamp ? `Imported ${formatDate(timestamp)}` : "No completed import yet"}
                  </p>
                </div>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard
          title="Board Pressure"
          description="Jump directly into the queues that need attention."
          actions={
            <div className="flex flex-wrap gap-3">
              <Link className="btn-primary" to="/board?board_filter=MOVE_IN_DANGER">
                Critical move-ins
              </Link>
              <Link className="btn-ghost" to="/board?board_filter=SLA_RISK">
                SLA risk
              </Link>
            </div>
          }
        >
          <MetricGrid
            metrics={[
              { label: "Vacant > 7 Days", value: workflow?.risk_metrics.vacant_over_7 ?? "—", tone: "warning" },
              { label: "SLA Breach", value: workflow?.risk_metrics.sla_breach ?? "—", tone: "danger" },
              { label: "Move-In ≤ 3 Days", value: workflow?.risk_metrics.move_in_soon ?? "—", tone: "danger" },
              { label: "Open Turnovers", value: workflow?.summary.total ?? "—" },
            ]}
          />
        </SectionCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          title="Missing Move-Out Queue"
          description="Rows from Pending Move-Ins that still need a turnover created."
          actions={
            <Link className="btn-ghost" to="/report-operations">
              Open Import Reports
            </Link>
          }
        >
          {workflow?.missing_move_outs?.length ? (
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="min-w-full text-sm">
                <thead className="bg-surface-2 text-left text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Unit</th>
                    <th className="px-4 py-3 font-medium">Move-In Date</th>
                    <th className="px-4 py-3 font-medium">Detected</th>
                  </tr>
                </thead>
                <tbody>
                  {workflow.missing_move_outs.slice(0, 6).map((row) => (
                    <tr key={row.row_id} className="border-t border-border">
                      <td className="px-4 py-3 font-medium text-text-strong">{row.unit_code_norm}</td>
                      <td className="px-4 py-3 text-text">{formatDate(row.move_in_date)}</td>
                      <td className="px-4 py-3 text-text">{formatDate(row.batch_created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted">No unresolved missing move-out rows.</p>
          )}
        </SectionCard>

        <SectionCard title="Today’s Critical Units" description="Same-day move-outs and move-ins that should not get buried in the board.">
          {workflow?.critical_units?.length ? (
            <div className="space-y-3">
              {workflow.critical_units.map((row) => (
                <Link
                  key={`${row.turnover_id}-${row.event}`}
                  to={`/turnovers/${row.turnover_id}`}
                  className="flex items-center justify-between rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm transition hover:border-border-strong hover:bg-surface-3"
                >
                  <span className="font-medium text-text-strong">{row.unit_code}</span>
                  <span className="text-muted">{row.event}</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No same-day move-in or move-out events on the active board.</p>
          )}
        </SectionCard>
      </div>
    </PageShell>
  );
}
