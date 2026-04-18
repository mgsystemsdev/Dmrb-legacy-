type StatusBadgeProps = {
  label: string;
  toneKey?: string;
};

const toneMap: Record<string, string> = {
  READY: "bg-green-50 text-green-700 ring-green-600/20",
  IN_PROGRESS: "bg-blue-50 text-blue-700 ring-blue-600/20",
  NOT_STARTED: "bg-slate-100 text-slate-700 ring-slate-500/20",
  BLOCKED: "bg-red-50 text-red-700 ring-red-600/20",
  NO_TASKS: "bg-slate-50 text-slate-500 ring-slate-400/20",
};

export function StatusBadge({ label, toneKey }: StatusBadgeProps) {
  const tone = toneMap[toneKey ?? label] ?? "bg-slate-100 text-slate-700 ring-slate-500/20";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${tone}`}>
      {label}
    </span>
  );
}
