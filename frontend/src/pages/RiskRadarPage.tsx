import { PageShell } from "../components/PageShell";

export function RiskRadarPage() {
  return (
    <PageShell
      title="Risk Radar"
      description="Route scaffold for the risk dashboard. This keeps navigation and auth stable while the API layer matures."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          Risk-level filters, search, and metrics will be added against dedicated endpoints.
        </p>
      </section>
    </PageShell>
  );
}
