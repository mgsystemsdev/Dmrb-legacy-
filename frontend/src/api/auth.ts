import { api } from "./client";
import type { AuthUser } from "../stores/useAuth";

/** React Query key for GET /auth/bootstrap-status */
export const AUTH_BOOTSTRAP_QUERY_KEY = ["bootstrap-status"] as const;

type LoginPayload = {
  username: string;
  password: string;
};

export type BootstrapStatus = {
  needs_bootstrap: boolean;
};

export async function getBootstrapStatus(): Promise<BootstrapStatus> {
  const { data } = await api.get<BootstrapStatus>("/auth/bootstrap-status");
  return data;
}

type BootstrapPayload = {
  username: string;
  password: string;
  password_confirm: string;
};

export async function bootstrapAdmin(payload: BootstrapPayload): Promise<AuthUser> {
  await api.post("/auth/bootstrap", {
    username: payload.username,
    password: payload.password,
    password_confirm: payload.password_confirm,
  });
  const user = await getMe();
  return user;
}

export async function login(payload: LoginPayload): Promise<AuthUser> {
  await api.post("/login", payload);
  const user = await getMe();
  return user;
}

export async function logout(): Promise<void> {
  await api.post("/logout");
}

export async function getMe(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>("/auth/me");
  return data;
}
