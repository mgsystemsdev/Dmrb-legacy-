import { useMemo, useState } from "react";
import { PageShell } from "../components/PageShell";
import { MetricGrid } from "../components/MetricGrid";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { useRiskRows } from "../api/useOperations";
import { usePropertyStore } from "../stores/useProperty";
import { formatDate } from "../lib/utils";

export function RiskRadarPage() {
  const propertyId = usePropertyStore((state) => state.propertyId);
  const riskQuery = useRiskRows(propertyId);
  const rows = riskQuery.data ?? [];
  const [phase, setPhase] = useState("All");
  const [level, setLevel] = useState("All");
  const [search, setSearch] = useState("");

  const phases = useMemo(
    () => ["All", ...Array.from(new Set(rows.map((row) => row.phase_code).filter(Boolean))).sort()],
    [rows],
  );

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (phase !== "All" && row.phase_code !== phase) {
        return false;
      }
      if (level !== "All" && row.risk_level !== level) {
        return false;
      }
      if (search.trim() && !row.unit_code.toLowerCase().includes(search.trim().toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [level, phase, rows, search]);

  const counts = useMemo(
    () => ({
      high: filtered.filter((row) => row.risk_level === "HIGH").length,
      medium: filtered.filter((row) => row.risk_level === "MEDIUM").length,
      low: filtered.filter((row) => row.risk_level === "LOW").length,
    }),
    [filtered],
  );

  return (
    <PageShell
      title="Risk Radar"
      description="Units at highest risk of missing a deadline."
      action={<PropertySelector />}
    >
      <SectionCard title="Filters">
        <div className="grid gap-4 md:grid-cols-[1fr_1fr_2fr]">
          <label className="block">
            <span className="label">Phase</span>
            <select
              value={phase}
              onChange={(event) => setPhase(event.target.value)}
              className="input"
            >
              {phases.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Risk Level</span>
            <select
              value={level}
              onChange={(event) => setLevel(event.target.value)}
              className="input"
            >
              {["All", "HIGH", "MEDIUM", "LOW"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Unit Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="input"
              placeholder="Search unit"
            />
          </label>
        </div>
      </SectionCard>

      <MetricGrid
        metrics={[
          { label: "Total Active Turnovers", value: filtered.length },
          { label: "High Risk", value: counts.high, tone: "danger" },
          { label: "Medium Risk", value: counts.medium, tone: "warning" },
          { label: "Low Risk", value: counts.low, tone: "success" },
        ]}
      />

      <SectionCard title="Risk Queue">
        {filtered.length ? (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-2 text-left text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Unit</th>
                  <th className="px-4 py-3 font-medium">Phase</th>
                  <th className="px-4 py-3 font-medium">Risk Level</th>
                  <th className="px-4 py-3 font-medium">Risk Score</th>
                  <th className="px-4 py-3 font-medium">Risk Reasons</th>
                  <th className="px-4 py-3 font-medium">Move-In Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={`${row.unit_code}-${row.risk_score}`} className="border-t border-border align-top">
                    <td className="px-4 py-3 font-medium text-text-strong">{row.unit_code}</td>
                    <td className="px-4 py-3 text-text">{row.phase_code || "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`chip ${
                          row.risk_level === "HIGH"
                            ? "bg-red-500/10 text-red-300 ring-red-400/20"
                            : row.risk_level === "MEDIUM"
                              ? "bg-amber-500/10 text-amber-300 ring-amber-400/20"
                              : "bg-emerald-500/10 text-emerald-300 ring-emerald-400/20"
                        }`}
                      >
                        {row.risk_level}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text">{row.risk_score}</td>
                    <td className="px-4 py-3 text-text">{row.risk_reasons.join(", ") || "—"}</td>
                    <td className="px-4 py-3 text-text">{formatDate(row.move_in_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted">No turnovers match the current Risk Radar filters.</p>
        )}
      </SectionCard>
    </PageShell>
  );
}
