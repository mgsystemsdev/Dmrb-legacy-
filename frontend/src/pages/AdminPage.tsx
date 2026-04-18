import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../api/client";
import {
  useAdminSettings,
  useAdminUsers,
  usePropertyStructure,
} from "../api/useOperations";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";

type AdminTab = "system" | "turnover" | "structure" | "users";

export function AdminPage() {
  const queryClient = useQueryClient();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const settingsQuery = useAdminSettings(true);
  const usersQuery = useAdminUsers(true);
  const structureQuery = usePropertyStructure(propertyId);
  const [activeTab, setActiveTab] = useState<AdminTab>("system");
  const [writesEnabled, setWritesEnabled] = useState(false);
  const [newPropertyName, setNewPropertyName] = useState("");
  const [moveOutDate, setMoveOutDate] = useState("");
  const [moveInDate, setMoveInDate] = useState("");
  const [phaseId, setPhaseId] = useState<number | null>(null);
  const [buildingId, setBuildingId] = useState<number | null>(null);
  const [unitId, setUnitId] = useState<number | null>(null);
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "validator" });

  useEffect(() => {
    if (typeof settingsQuery.data?.enable_db_write === "boolean") {
      setWritesEnabled(settingsQuery.data.enable_db_write);
    }
  }, [settingsQuery.data?.enable_db_write]);

  const settingsMutation = useMutation({
    mutationFn: async (enableDbWrite: boolean) => {
      await api.patch("/operations/admin/settings", { enable_db_write: enableDbWrite });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      toast.success("System settings updated");
    },
    onError: () => toast.error("Settings update failed"),
  });

  const propertyMutation = useMutation({
    mutationFn: async () => {
      await api.post("/operations/admin/properties", { name: newPropertyName });
    },
    onSuccess: async () => {
      setNewPropertyName("");
      await queryClient.invalidateQueries({ queryKey: ["properties"] });
      toast.success("Property created");
    },
    onError: () => toast.error("Property creation failed"),
  });

  const turnoverMutation = useMutation({
    mutationFn: async () => {
      if (!propertyId || !unitId || !moveOutDate) {
        throw new Error("Property, unit, and move-out date are required");
      }
      await api.post(`/turnovers?property_id=${propertyId}`, {
        unit_id: unitId,
        move_out_date: moveOutDate,
        move_in_date: moveInDate || null,
      });
    },
    onSuccess: () => toast.success("Turnover created"),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Turnover creation failed"),
  });

  const createUserMutation = useMutation({
    mutationFn: async () => {
      await api.post("/operations/admin/users", newUser);
    },
    onSuccess: async () => {
      setNewUser({ username: "", password: "", role: "validator" });
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User created");
    },
    onError: () => toast.error("User create failed"),
  });

  const updateUserMutation = useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload: Record<string, string | boolean> }) => {
      await api.patch(`/operations/admin/users/${userId}`, payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User updated");
    },
    onError: () => toast.error("User update failed"),
  });

  const tabs: Array<{ key: AdminTab; label: string }> = [
    { key: "system", label: "System" },
    { key: "turnover", label: "Add Turnover" },
    { key: "structure", label: "Property Structure" },
    { key: "users", label: "Users" },
  ];

  return (
    <PageShell
      title="Admin"
      description="Manage properties, users, manual turnovers, and system settings."
      action={<PropertySelector />}
    >
      <SectionCard title="Admin Tabs">
        <div className="tab-group flex-wrap">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`tab-item ${activeTab === tab.key ? "tab-item-active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </SectionCard>

      {activeTab === "system" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="System Settings">
            <label className="flex items-center gap-3 text-sm font-medium text-text">
              <input
                type="checkbox"
                checked={writesEnabled}
                onChange={(event) => {
                  setWritesEnabled(event.target.checked);
                  settingsMutation.mutate(event.target.checked);
                }}
              />
              Enable DB writes
            </label>
          </SectionCard>

          <SectionCard title="Create Property">
            <div className="flex gap-3">
              <input
                value={newPropertyName}
                onChange={(event) => setNewPropertyName(event.target.value)}
                className="input flex-1"
                placeholder="Property name"
              />
              <button type="button" onClick={() => propertyMutation.mutate()} className="btn-primary">
                Create
              </button>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "turnover" ? (
        <AddTurnoverSection
          propertyId={propertyId}
          moveOutDate={moveOutDate}
          moveInDate={moveInDate}
          onMoveOutDateChange={setMoveOutDate}
          onMoveInDateChange={setMoveInDate}
          onPhaseIdChange={setPhaseId}
          onBuildingIdChange={setBuildingId}
          onUnitIdChange={setUnitId}
          phaseId={phaseId}
          buildingId={buildingId}
          unitId={unitId}
          onSubmit={() => turnoverMutation.mutate()}
        />
      ) : null}

      {activeTab === "structure" ? (
        <SectionCard title="Property Structure">
          <div className="space-y-4">
            {structureQuery.data?.structure.map((phase) => (
              <details key={phase.phase.phase_id} className="rounded-xl border border-border bg-surface-2 px-4 py-3">
                <summary className="cursor-pointer font-medium text-text-strong">
                  {phase.phase.name ?? phase.phase.phase_code}
                </summary>
                <div className="mt-4 space-y-3">
                  {phase.buildings.map((building) => (
                    <details key={building.building.building_id} className="rounded-lg border border-border bg-surface-3 px-4 py-3">
                      <summary className="cursor-pointer text-sm font-medium text-text">
                        {building.building.name ?? building.building.building_code}
                      </summary>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {building.units.map((unit) => (
                          <span key={unit.unit_id} className="rounded-full bg-surface-2 px-3 py-1 text-xs font-medium text-muted ring-1 ring-inset ring-border">
                            {unit.unit_code_norm}
                          </span>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "users" ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="Create User">
            <form
              className="space-y-4"
              onSubmit={(event: FormEvent<HTMLFormElement>) => {
                event.preventDefault();
                createUserMutation.mutate();
              }}
            >
              <input value={newUser.username} onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))} className="input" placeholder="Username" />
              <input value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} className="input" placeholder="Password" type="password" />
              <select value={newUser.role} onChange={(event) => setNewUser((current) => ({ ...current, role: event.target.value }))} className="input">
                <option value="validator">validator</option>
                <option value="admin">admin</option>
              </select>
              <button type="submit" className="btn-primary">
                Create User
              </button>
            </form>
          </SectionCard>

          <SectionCard title="Existing Users">
            <div className="space-y-3">
              {usersQuery.data?.map((user) => (
                <div key={user.user_id} className="rounded-xl border border-border bg-surface-2 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-text-strong">{user.username}</p>
                      <p className="text-sm text-muted">
                        {user.role} | {user.is_active ? "active" : "inactive"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => updateUserMutation.mutate({ userId: user.user_id, payload: { role: user.role === "admin" ? "validator" : "admin" } })} className="btn-ghost">
                        Toggle Role
                      </button>
                      <button type="button" onClick={() => updateUserMutation.mutate({ userId: user.user_id, payload: { is_active: !user.is_active } })} className="btn-ghost">
                        {user.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      ) : null}
    </PageShell>
  );
}

function AddTurnoverSection({
  propertyId,
  phaseId,
  buildingId,
  unitId,
  moveOutDate,
  moveInDate,
  onPhaseIdChange,
  onBuildingIdChange,
  onUnitIdChange,
  onMoveOutDateChange,
  onMoveInDateChange,
  onSubmit,
}: {
  propertyId: number | null;
  phaseId: number | null;
  buildingId: number | null;
  unitId: number | null;
  moveOutDate: string;
  moveInDate: string;
  onPhaseIdChange: (value: number | null) => void;
  onBuildingIdChange: (value: number | null) => void;
  onUnitIdChange: (value: number | null) => void;
  onMoveOutDateChange: (value: string) => void;
  onMoveInDateChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const [phases, setPhases] = useState<Array<{ phase_id: number; phase_code: string; name?: string }>>([]);
  const [buildings, setBuildings] = useState<Array<{ building_id: number; building_code: string; name?: string }>>([]);
  const [units, setUnits] = useState<Array<{ unit_id: number; unit_code_norm: string }>>([]);

  useEffect(() => {
    if (!propertyId) {
      setPhases([]);
      return;
    }
    api.get<Array<{ phase_id: number; phase_code: string; name?: string }>>(`/properties/${propertyId}/phases`).then((response) => {
      setPhases(response.data);
      if (!phaseId && response.data.length) {
        onPhaseIdChange(response.data[0].phase_id);
      }
    });
  }, [onPhaseIdChange, phaseId, propertyId]);

  useEffect(() => {
    if (!phaseId) {
      setBuildings([]);
      return;
    }
    api.get<Array<{ building_id: number; building_code: string; name?: string }>>(`/phases/${phaseId}/buildings`).then((response) => {
      setBuildings(response.data);
      if (response.data.length) {
        onBuildingIdChange(response.data[0].building_id);
      }
    });
  }, [onBuildingIdChange, phaseId]);

  useEffect(() => {
    if (!buildingId || !propertyId) {
      setUnits([]);
      return;
    }
    api.get<Array<{ unit_id: number; unit_code_norm: string }>>(`/buildings/${buildingId}/units`, {
      params: { property_id: propertyId },
    }).then((response) => {
      setUnits(response.data);
      if (response.data.length) {
        onUnitIdChange(response.data[0].unit_id);
      }
    });
  }, [buildingId, onUnitIdChange, propertyId]);

  return (
    <SectionCard title="Add Turnover" description="Select a phase, building, and unit.">
      <div className="grid gap-4 md:grid-cols-3">
        <select value={phaseId ?? ""} onChange={(event) => onPhaseIdChange(Number(event.target.value))} className="input">
          {phases.map((phase) => (
            <option key={phase.phase_id} value={phase.phase_id}>
              {phase.name ?? phase.phase_code}
            </option>
          ))}
        </select>
        <select value={buildingId ?? ""} onChange={(event) => onBuildingIdChange(Number(event.target.value))} className="input">
          {buildings.map((building) => (
            <option key={building.building_id} value={building.building_id}>
              {building.name ?? building.building_code}
            </option>
          ))}
        </select>
        <select value={unitId ?? ""} onChange={(event) => onUnitIdChange(Number(event.target.value))} className="input">
          {units.map((unit) => (
            <option key={unit.unit_id} value={unit.unit_id}>
              {unit.unit_code_norm}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <input type="date" value={moveOutDate} onChange={(event) => onMoveOutDateChange(event.target.value)} className="input" />
        <input type="date" value={moveInDate} onChange={(event) => onMoveInDateChange(event.target.value)} className="input" />
        <button type="button" onClick={onSubmit} className="btn-primary">
          Add Turnover
        </button>
      </div>
    </SectionCard>
  );
}
