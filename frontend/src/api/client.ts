import axios from "axios";
import { useAuthStore } from "../stores/useAuth";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearSession();

      const path = window.location.pathname;
      const reqUrl = String(error.config?.url ?? "");

      if (path === "/login" || path === "/setup") {
        return Promise.reject(error);
      }
      if (reqUrl === "/auth/me" || reqUrl === "/auth/bootstrap-status") {
        return Promise.reject(error);
      }

      if (path !== "/login" && path !== "/setup") {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.assign(`/login?next=${next}`);
      }
    }

    return Promise.reject(error);
  },
);
