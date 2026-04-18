type Metric = {
  label: string;
  value: string | number;
  tone?: "default" | "danger" | "warning" | "success";
};

const toneClass: Record<NonNullable<Metric["tone"]>, string> = {
  default: "text-text-strong",
  danger: "text-red-300",
  warning: "text-amber-300",
  success: "text-emerald-300",
};

export function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-xl border border-border bg-surface-2 px-4 py-4 shadow-hairline"
        >
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted">
            {metric.label}
          </p>
          <p
            className={`mt-3 text-3xl font-bold tracking-tight ${toneClass[metric.tone ?? "default"]}`}
          >
            {metric.value}
          </p>
        </div>
      ))}
    </div>
  );
}
