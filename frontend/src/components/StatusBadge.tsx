type StatusBadgeProps = {
  label: string;
  toneKey?: string;
};

const toneMap: Record<string, string> = {
  READY: "bg-emerald-500/10 text-emerald-300 ring-emerald-400/20",
  IN_PROGRESS: "bg-sky-500/10 text-sky-300 ring-sky-400/20",
  NOT_STARTED: "bg-surface-3 text-muted ring-border",
  BLOCKED: "bg-red-500/10 text-red-300 ring-red-400/20",
  NO_TASKS: "bg-surface-2 text-muted ring-border",
};

export function StatusBadge({ label, toneKey }: StatusBadgeProps) {
  const tone = toneMap[toneKey ?? label] ?? "bg-surface-3 text-muted ring-border";

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${tone}`}
    >
      {label}
    </span>
  );
}
