import { PageShell } from "../components/PageShell";

export function ReportOperationsPage() {
  return (
    <PageShell
      title="Report Operations"
      description="Route shell for import diagnostics, missing move-out workflows, and export tooling."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          File upload flows and export jobs will be layered onto this screen once the remaining API endpoints are finalized.
        </p>
      </section>
    </PageShell>
  );
}
