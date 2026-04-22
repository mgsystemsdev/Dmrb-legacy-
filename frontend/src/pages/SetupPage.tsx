import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AUTH_BOOTSTRAP_QUERY_KEY, bootstrapAdmin, getBootstrapStatus } from "../api/auth";
import { useAuthStore } from "../stores/useAuth";

export function SetupPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSession = useAuthStore((state) => state.setSession);

  const statusQuery = useQuery({
    queryKey: AUTH_BOOTSTRAP_QUERY_KEY,
    queryFn: getBootstrapStatus,
  });

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: bootstrapAdmin,
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: AUTH_BOOTSTRAP_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      setSession({ user });
      toast.success("Admin account created — you're signed in");
      navigate("/board", { replace: true });
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Setup failed");
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const u = username.trim();
    if (!u) {
      toast.error("Enter a username");
      return;
    }
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    if (password !== passwordConfirm) {
      toast.error("Passwords do not match");
      return;
    }
    mutation.mutate({
      username: u,
      password,
      password_confirm: passwordConfirm,
    });
  };

  if (statusQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <p className="text-sm text-muted">Loading…</p>
      </div>
    );
  }

  if (statusQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <p className="text-sm text-red-200">Could not load setup status.</p>
      </div>
    );
  }

  if (!statusQuery.data?.needs_bootstrap) {
    const d = statusQuery.data;
    let hint = "Setup is not available. Use sign in, or check server config.";
    if (d?.reason === "auth_disabled") {
      hint =
        "API auth is disabled (AUTH_DISABLED). First-run setup is not offered; the API runs without normal login.";
    } else if (d?.reason === "users_exist") {
      hint = `An account already exists in the database (user count: ${d.user_count}).`;
    } else if (d?.reason === "production_requires_ALLOW_API_BOOTSTRAP") {
      hint =
        "Production mode blocks bootstrap unless ALLOW_API_BOOTSTRAP is set, or set IS_PRODUCTION false for local.";
    } else if (d?.reason === "user_count_error") {
      hint = "Could not read the app_user table; check the database connection.";
    }
    return (
      <div className="mx-auto max-w-md px-4 py-10 text-center">
        <p className="text-sm text-muted">{hint}</p>
        <p className="mt-2 text-left text-xs text-muted/80 font-mono">
          needs_bootstrap=false · count={d?.user_count ?? "?"}
          {d?.is_production ? " · production" : ""}
          {d?.allow_api_bootstrap ? " · allow_bootstrap" : ""}
        </p>
        <button type="button" className="btn-primary mt-4" onClick={() => navigate("/login", { replace: true })}>
          Go to sign in
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-8 shadow-panel">
        <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted">DMRB</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-text-strong">Create admin account</h1>
        <p className="mt-2 text-sm text-muted">First-time setup. Choose your username and password (enter the password twice).</p>

        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="label">Admin username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input"
              autoComplete="username"
              required
            />
          </label>
          <label className="block">
            <span className="label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label className="block">
            <span className="label">Confirm password</span>
            <input
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="input"
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <p className="text-xs text-muted">Minimum 8 characters. Your account is stored in the database (<code className="text-text">app_user</code> table).</p>
          <button type="submit" disabled={mutation.isPending} className="btn-primary w-full">
            {mutation.isPending ? "Saving…" : "Create account & sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
