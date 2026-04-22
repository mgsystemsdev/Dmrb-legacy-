import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageShell } from "../components/PageShell";
import { MetricGrid } from "../components/MetricGrid";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { useScopedPropertyPhases } from "../api/usePhaseScope";
import { useFlagBridge } from "../api/useOperations";
import { usePropertyStore } from "../stores/useProperty";
import { formatDate } from "../lib/utils";

export function FlagBridgePage() {
  const navigate = useNavigate();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const { filteredPhases, isPending: phasesScopePending } = useScopedPropertyPhases(propertyId);
  const flagBridgeQuery = useFlagBridge(propertyId);
  const rows = flagBridgeQuery.data?.rows ?? [];
  const metrics = flagBridgeQuery.data?.metrics;
  const [phase, setPhase] = useState("All");
  const [bridge, setBridge] = useState("All");
  const [value, setValue] = useState("All");

  useEffect(() => {
    if (filteredPhases == null) {
      return;
    }
    if (phase === "All") {
      return;
    }
    if (filteredPhases.length === 0) {
      setPhase("All");
      return;
    }
    if (!filteredPhases.some((p) => p.phase_code === phase)) {
      setPhase("All");
    }
  }, [filteredPhases, phase]);

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      const agreements = row.agreements ?? {};
      const hasBreach = Object.values(agreements).includes("RED");
      if (phase !== "All" && (row.unit?.phase_code ?? "") !== phase) {
        return false;
      }
      if (bridge !== "All") {
        const key =
          bridge === "Insp Breach"
            ? "inspection"
            : bridge === "SLA Breach"
              ? "sla"
              : bridge === "SLA MI Breach"
                ? "move_in"
                : "plan";
        if (agreements[key] !== "RED") {
          return false;
        }
      }
      if (value === "Yes" && !hasBreach) {
        return false;
      }
      if (value === "No" && hasBreach) {
        return false;
      }
      return true;
    });
  }, [bridge, phase, rows, value]);

  return (
    <PageShell
      title="Flag Bridge"
      description="Units that have missed an SLA, inspection, or move-in target."
      action={<PropertySelector />}
    >
      <SectionCard title="Filters">
        <div className="grid gap-4 md:grid-cols-3">
          <label className="block">
            <span className="label">Phase</span>
            <select
              value={phase}
              onChange={(event) => setPhase(event.target.value)}
              className="input"
              disabled={phasesScopePending || (filteredPhases != null && filteredPhases.length === 0)}
            >
              <option value="All">All</option>
              {phasesScopePending && phase !== "All" ? (
                <option value={phase}>{phase}</option>
              ) : null}
              {!phasesScopePending && filteredPhases
                ? [...filteredPhases]
                    .sort((a, b) => a.phase_code.localeCompare(b.phase_code))
                    .map((p) => (
                      <option key={p.phase_id} value={p.phase_code}>
                        {p.name && p.name.trim() ? p.name.trim() : p.phase_code}
                      </option>
                    ))
                : null}
            </select>
          </label>
          <label className="block">
            <span className="label">Flag Bridge</span>
            <select value={bridge} onChange={(event) => setBridge(event.target.value)} className="input">
              {["All", "Insp Breach", "SLA Breach", "SLA MI Breach", "Plan Breach"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Value</span>
            <select value={value} onChange={(event) => setValue(event.target.value)} className="input">
              {["All", "Yes", "No"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </SectionCard>

      <MetricGrid
        metrics={[
          { label: "Total Units", value: filtered.length || metrics?.total || 0 },
          { label: "Violations", value: metrics?.violations ?? 0, tone: "danger" },
          { label: "Units w/ Breach", value: metrics?.units_with_breach ?? 0, tone: "warning" },
        ]}
      />

      <SectionCard title="Breach Table" description="Click any row to jump into turnover detail.">
        {filtered.length ? (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-2 text-left text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Unit</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">DV</th>
                  <th className="px-4 py-3 font-medium">Move-In</th>
                  <th className="px-4 py-3 font-medium">Ready Date</th>
                  <th className="px-4 py-3 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const flags = Object.entries(row.agreements ?? {})
                    .filter(([, status]) => status === "RED")
                    .map(([key]) => key.replace("_", " "));
                  return (
                    <tr
                      key={row.turnover.turnover_id}
                      className="cursor-pointer border-t border-border transition hover:bg-surface-2"
                      onClick={() => navigate(`/turnovers/${row.turnover.turnover_id}`)}
                    >
                      <td className="px-4 py-3 font-medium text-text-strong">{row.unit?.unit_code_norm ?? "—"}</td>
                      <td className="px-4 py-3 text-text">{row.turnover.lifecycle_phase}</td>
                      <td className="px-4 py-3 text-text">{row.turnover.days_since_move_out ?? "—"}</td>
                      <td className="px-4 py-3 text-text">{formatDate(row.turnover.move_in_date)}</td>
                      <td className="px-4 py-3 text-text">{formatDate(row.turnover.report_ready_date)}</td>
                      <td className="px-4 py-3 text-text">{flags.join(", ") || "Clear"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted">No rows match the current Flag Bridge filters.</p>
        )}
      </SectionCard>
    </PageShell>
  );
}
