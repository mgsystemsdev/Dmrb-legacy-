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

function formatRole(role?: string) {
  if (!role) return "No role";
  const normalized = role.toLowerCase().replace(/[_\s-]+/g, " ").trim();
  if (normalized.includes("admin")) return "Admin";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

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
    <aside className="border-b border-border bg-surface px-5 py-6 text-text lg:min-h-screen lg:border-b-0 lg:border-r">
      <div className="mb-8">
        <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted">
          DMRB
        </p>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-text-strong">
          Operations Console
        </h1>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `group relative block rounded-md px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-surface-3 text-text-strong shadow-hairline"
                  : "text-muted hover:bg-surface-2 hover:text-text"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`absolute inset-y-1 left-0 w-[3px] rounded-full transition ${
                    isActive ? "bg-white" : "bg-transparent"
                  }`}
                />
                <span className="ml-2">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-8 rounded-xl border border-border bg-surface-2 p-4 shadow-hairline">
        <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted">
          {formatRole(user?.role)}
        </p>
        <button
          type="button"
          onClick={handleLogout}
          className="btn-ghost mt-4 w-full"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
