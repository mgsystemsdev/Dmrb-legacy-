import { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../stores/useAuth";

export function RequireAuth({ children }: PropsWithChildren) {
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasCheckedAuth = useAuthStore((state) => state.hasCheckedAuth);

  if (!hasCheckedAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <div className="rounded-xl border border-border bg-surface px-6 py-4 text-sm text-muted shadow-panel">
          Checking session...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  return <>{children}</>;
}
