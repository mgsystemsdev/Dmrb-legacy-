import { NavLink, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { logout } from "../api/auth";
import { useAuthStore } from "../stores/useAuth";

const navItems = [
  { to: "/morning-workflow", label: "Morning Workflow" },
  { to: "/board", label: "Board" },
  { to: "/flag-bridge", label: "Flag Bridge" },
  { to: "/risk-radar", label: "Risk Radar" },
  { to: "/operations-schedule", label: "Operations Schedule" },
  { to: "/report-operations", label: "Report Operations" },
  { to: "/ai-agent", label: "AI Agent" },
  { to: "/admin", label: "Admin" },
];

export function Sidebar() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);

  const handleLogout = async () => {
    await logout();
    clearSession();
    toast.success("Signed out");
    navigate("/login");
  };

  return (
    <aside className="border-b border-slate-200 bg-ink px-5 py-6 text-white lg:min-h-screen lg:border-b-0 lg:border-r lg:border-slate-800">
      <div className="mb-8">
        <p className="text-xs uppercase tracking-[0.28em] text-orange-300">DMRB Legacy</p>
        <h1 className="mt-2 text-2xl font-semibold">Operations Console</h1>
        <p className="mt-2 text-sm text-slate-300">
          React shell for the FastAPI migration.
        </p>
      </div>

      <nav className="space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `block rounded-xl px-4 py-3 text-sm transition ${
                isActive ? "bg-white text-ink shadow-panel" : "text-slate-200 hover:bg-slate-800"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-8 rounded-2xl border border-slate-700 bg-slate-900/60 p-4">
        <p className="text-sm font-medium">{user?.username ?? "Unknown user"}</p>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{user?.role ?? "No role"}</p>
        <button
          type="button"
          onClick={handleLogout}
          className="mt-4 w-full rounded-xl border border-slate-600 px-3 py-2 text-sm text-slate-100 transition hover:border-orange-300 hover:text-orange-200"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
