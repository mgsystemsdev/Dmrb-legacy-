import { Link } from "react-router-dom";
import { PageShell } from "../components/PageShell";

export function MorningWorkflowPage() {
  return (
    <PageShell
      title="Morning Workflow"
      description="Screen placeholder for the migration. Route and layout exist so board-filter navigation can be added without reworking the app shell."
    >
      <section className="grid gap-6 md:grid-cols-3">
        <div className="rounded-[28px] bg-white p-6 shadow-panel">
          <h2 className="text-lg font-semibold text-ink">Priority summary</h2>
          <p className="mt-2 text-sm text-slate-600">Wire this to the board aggregates in Phase 4.</p>
        </div>
        <div className="rounded-[28px] bg-white p-6 shadow-panel">
          <h2 className="text-lg font-semibold text-ink">Repair queue</h2>
          <p className="mt-2 text-sm text-slate-600">State handoff will move to URL params and query invalidation.</p>
        </div>
        <div className="rounded-[28px] bg-white p-6 shadow-panel">
          <h2 className="text-lg font-semibold text-ink">Quick actions</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link className="rounded-xl bg-ink px-4 py-2 text-sm font-medium text-white" to="/board">
              Open Board
            </Link>
            <Link className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700" to="/flag-bridge">
              Open Flag Bridge
            </Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
