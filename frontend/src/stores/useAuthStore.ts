import { create } from 'zustand';
import { tokenStorage } from '@/auth/tokenStorage';
import type { CurrentUserResponse } from '@/types/auth';

interface AuthState {
  user: CurrentUserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: CurrentUserResponse | null) => void;
  setLoading: (isLoading: boolean) => void;
  setSession: (user: CurrentUserResponse, accessToken: string, refreshToken: string) => void;
  logout: () => void;
  hasPermission: (permissionCode: string) => boolean;
  hasRole: (roleName: string) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: tokenStorage.hasTokens(),
  isLoading: true,

  setUser: (user) => {
    set({
      user,
      isAuthenticated: !!user,
      isLoading: false,
    });
  },

  setLoading: (isLoading) => {
    set({ isLoading });
  },

  setSession: (user, accessToken, refreshToken) => {
    tokenStorage.setTokens(accessToken, refreshToken);
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: () => {
    tokenStorage.clearTokens();
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  hasPermission: (permissionCode: string): boolean => {
    const user = get().user;
    if (!user) return false;
    if (user.is_superuser) return true;
    return user.permissions.includes(permissionCode);
  },

  hasRole: (roleName: string): boolean => {
    const user = get().user;
    if (!user) return false;
    if (user.is_superuser) return true;
    return user.roles.includes(roleName);
  },
}));
