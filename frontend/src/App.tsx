import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getMe } from "./api/auth";
import { router } from "./router";
import { useAuthStore } from "./stores/useAuth";

function AuthBootstrap() {
  const setSession = useAuthStore((state) => state.setSession);
  const clearSession = useAuthStore((state) => state.clearSession);
  const markChecked = useAuthStore((state) => state.markChecked);

  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getMe,
    retry: false,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (query.data) {
      setSession({ user: query.data });
    } else if (query.isSuccess) {
      markChecked();
    }
  }, [markChecked, query.data, query.isSuccess, setSession]);

  useEffect(() => {
    if (query.isError) {
      clearSession();
    }
  }, [clearSession, query.isError]);

  return <RouterProvider router={router} />;
}

export default function App() {
  return <AuthBootstrap />;
}
