import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Me = {
  id: string;
  email: string;
  full_name: string;
  title?: string;
  avatar_url?: string;
  roles: string[];
  permissions: string[];
  student_id?: string | null;
  instructor_id?: string | null;
  organization: { id: string; name: string; code: string; timezone: string };
};

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  me: Me | null;
  setTokens: (a: string, r: string) => void;
  setMe: (m: Me | null) => void;
  logout: () => void;
};

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      me: null,
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setMe: (me) => set({ me }),
      logout: () => set({ accessToken: null, refreshToken: null, me: null }),
    }),
    { name: "edumaster-auth", partialize: (s) => ({ refreshToken: s.refreshToken, accessToken: s.accessToken }) },
  ),
);

export const can = (perm: string) => !!useAuth.getState().me?.permissions.includes(perm);
export function usePerm(perm: string) {
  return useAuth((s) => !!s.me?.permissions.includes(perm));
}
