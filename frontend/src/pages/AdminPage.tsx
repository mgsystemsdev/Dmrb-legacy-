import { PageShell } from "../components/PageShell";

export function AdminPage() {
  return (
    <PageShell
      title="Admin"
      description="Control-plane placeholder for phase scope, imports, exports, and user management."
    >
      <section className="rounded-[28px] bg-white p-6 shadow-panel">
        <p className="text-sm text-slate-600">
          This route exists now so the shell, auth, and navigation do not need to be reworked later.
        </p>
      </section>
    </PageShell>
  );
}
