import { PropsWithChildren, ReactNode } from "react";

type PageShellProps = PropsWithChildren<{
  title: string;
  description: string;
  eyebrow?: string;
  action?: ReactNode;
}>;

export function PageShell({
  title,
  description,
  eyebrow,
  action,
  children,
}: PageShellProps) {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-10">
      <header className="relative flex flex-col gap-4 overflow-hidden rounded-2xl border border-border bg-surface-elevated p-6 shadow-panel shadow-hairline-strong sm:flex-row sm:items-end sm:justify-between">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        <div>
          {eyebrow ? (
            <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-text-strong">
            {title}
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}
