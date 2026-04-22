import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AUTH_BOOTSTRAP_QUERY_KEY, getBootstrapStatus, getMe } from "./api/auth";
import { router } from "./router";
import { useAuthStore } from "./stores/useAuth";

function AuthBootstrap() {
  const setSession = useAuthStore((state) => state.setSession);
  const clearSession = useAuthStore((state) => state.clearSession);

  const bootstrapQuery = useQuery({
    queryKey: AUTH_BOOTSTRAP_QUERY_KEY,
    queryFn: getBootstrapStatus,
  });

  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    enabled: Boolean(bootstrapQuery.isSuccess && !bootstrapQuery.data?.needs_bootstrap),
    retry: false,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!bootstrapQuery.isSuccess) {
      return;
    }
    if (bootstrapQuery.data?.needs_bootstrap) {
      clearSession();
    }
  }, [bootstrapQuery.isSuccess, bootstrapQuery.data?.needs_bootstrap, clearSession]);

  useEffect(() => {
    if (!bootstrapQuery.isSuccess || bootstrapQuery.data?.needs_bootstrap) {
      return;
    }
    if (meQuery.data) {
      setSession({ user: meQuery.data });
    } else if (meQuery.isError) {
      clearSession();
    }
  }, [
    bootstrapQuery.isSuccess,
    bootstrapQuery.data?.needs_bootstrap,
    meQuery.data,
    meQuery.isError,
    setSession,
    clearSession,
  ]);

  return <RouterProvider router={router} />;
}

export default function App() {
  return <AuthBootstrap />;
}
