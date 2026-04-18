import { PageShell } from "../components/PageShell";

export function AiAgentPage() {
  return (
    <PageShell
      title="AI Agent"
      description="Placeholder for the future chat UI. The SPA now has a durable route and shell for later streaming integration."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          Session persistence and streaming messages are deferred to the AI phase.
        </p>
      </section>
    </PageShell>
  );
}
