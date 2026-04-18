import { PageShell } from "../components/PageShell";

export function OperationsSchedulePage() {
  return (
    <PageShell
      title="Operations Schedule"
      description="Placeholder for the manager/vendor schedule split. React Query and the constants layer are in place for the eventual task scheduling UI."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          Editable schedule grid and role-based views will be implemented in a later phase.
        </p>
      </section>
    </PageShell>
  );
}
