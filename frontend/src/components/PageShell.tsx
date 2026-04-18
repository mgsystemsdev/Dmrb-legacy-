import { PropsWithChildren, ReactNode } from "react";

type PageShellProps = PropsWithChildren<{
  title: string;
  description: string;
  action?: ReactNode;
}>;

export function PageShell({ title, description, action, children }: PageShellProps) {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-10">
      <header className="flex flex-col gap-4 rounded-[28px] bg-white p-6 shadow-panel sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-orange-600">Phase 2</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">{description}</p>
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}
