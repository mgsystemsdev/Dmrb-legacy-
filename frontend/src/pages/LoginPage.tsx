import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { login } from "../api/auth";
import { useAuthStore } from "../stores/useAuth";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((state) => state.setSession);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const search = new URLSearchParams(location.search);
  const next = search.get("next") ?? "/board";

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      setSession({ user });
      toast.success("Signed in");
      navigate(next, { replace: true });
    },
    onError: () => {
      toast.error("Invalid username or password");
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.mutate({ username, password });
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md rounded-[28px] bg-white p-8 shadow-panel">
        <p className="text-xs uppercase tracking-[0.28em] text-orange-600">DMRB Legacy</p>
        <h1 className="mt-3 text-3xl font-semibold text-ink">Sign in</h1>
        <p className="mt-2 text-sm text-slate-600">
          FastAPI issues the session cookie. Zustand stores the active user profile for the React shell.
        </p>

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Username</span>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2"
              autoComplete="username"
              required
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2"
              autoComplete="current-password"
              required
            />
          </label>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full rounded-xl bg-ink px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {mutation.isPending ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
