import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type AuthUser = {
  user_id: number | string;
  username: string;
  role: string;
  access_mode?: string;
};

type AuthState = {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  hasCheckedAuth: boolean;
  setSession: (payload: { user: AuthUser; token?: string | null }) => void;
  clearSession: () => void;
  markChecked: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      hasCheckedAuth: false,
      setSession: ({ user, token = null }) =>
        set({
          user,
          token,
          isAuthenticated: true,
          hasCheckedAuth: true,
        }),
      clearSession: () =>
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          hasCheckedAuth: true,
        }),
      markChecked: () => set({ hasCheckedAuth: true }),
    }),
    {
      name: "dmrb-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
