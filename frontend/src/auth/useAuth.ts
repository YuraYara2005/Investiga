import { useAuthStore } from '@/stores/useAuthStore';

/**
 * Hook providing access to authentication state, claims, and actions.
 */
export function useAuth() {
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoading = useAuthStore((state) => state.isLoading);
  const setSession = useAuthStore((state) => state.setSession);
  const logout = useAuthStore((state) => state.logout);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const hasRole = useAuthStore((state) => state.hasRole);

  return {
    user,
    isAuthenticated,
    isLoading,
    isSuperuser: user?.is_superuser ?? false,
    roles: user?.roles ?? [],
    permissions: user?.permissions ?? [],
    setSession,
    logout,
    hasPermission,
    hasRole,
  };
}
