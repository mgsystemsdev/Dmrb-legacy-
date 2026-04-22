import { PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import { AUTH_BOOTSTRAP_QUERY_KEY, getBootstrapStatus } from "../api/auth";
import { useAuthStore } from "../stores/useAuth";

export function RequireAuth({ children }: PropsWithChildren) {
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasCheckedAuth = useAuthStore((state) => state.hasCheckedAuth);

  const bootstrapQuery = useQuery({
    queryKey: AUTH_BOOTSTRAP_QUERY_KEY,
    queryFn: getBootstrapStatus,
    enabled: hasCheckedAuth && !isAuthenticated,
    staleTime: 60_000,
  });

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
    if (bootstrapQuery.isLoading || bootstrapQuery.isFetching) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
          <div className="rounded-xl border border-border bg-surface px-6 py-4 text-sm text-muted shadow-panel">
            Checking access…
          </div>
        </div>
      );
    }
    if (bootstrapQuery.data?.needs_bootstrap) {
      return <Navigate to="/setup" replace />;
    }
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  return <>{children}</>;
}
