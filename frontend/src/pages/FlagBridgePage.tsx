import { PageShell } from "../components/PageShell";

export function FlagBridgePage() {
  return (
    <PageShell
      title="Flag Bridge"
      description="Placeholder route for the breach-focused grid. The final screen will replace the Streamlit table with read-only AG Grid plus deep links into turnover detail."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          Filters, metrics, and breach categories will land here in Phase 4.
        </p>
      </section>
    </PageShell>
  );
}
