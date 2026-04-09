import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  permissions: string[];
  preferences?: {
    notifications_enabled?: boolean;
    [key: string]: any;
  };
}

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (user: User, token: string, refreshToken: string) => void;
  setTokens: (token: string, refreshToken: string) => void;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      login: (user, token, refreshToken) => set({ user, token, refreshToken, isAuthenticated: true }),
      setTokens: (token, refreshToken) => set({ token, refreshToken }),
      logout: () => {
        set({ user: null, token: null, refreshToken: null, isAuthenticated: false });
        localStorage.removeItem('citms_auth_storage');
      },
      hasPermission: (permission) => {
        const user = get().user;
        if (!user) return false;
        // Module 6: Strict Permission Check (Anti-Role Bypass)
        return user.permissions.includes(permission);
      },
    }),
    {
      name: 'citms_auth_storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
