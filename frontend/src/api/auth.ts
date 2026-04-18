import { api } from "./client";
import type { AuthUser } from "../stores/useAuth";

type LoginPayload = {
  username: string;
  password: string;
};

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
