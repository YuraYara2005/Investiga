import React, { createContext, useContext, useEffect } from 'react';
import { useAuthStore } from '@/stores/useAuthStore';
import { authService } from '@/services/authService';
import { tokenStorage } from '@/auth/tokenStorage';

interface AuthContextValue {
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  isLoading: true,
  isAuthenticated: false,
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, setUser, setLoading, logout } = useAuthStore();

  useEffect(() => {
    let isMounted = true;

    async function bootstrapSession() {
      if (!tokenStorage.hasTokens()) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await authService.getCurrentUser();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch {
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    bootstrapSession();

    // Listen for custom session-expired event emitted by interceptors
    const handleSessionExpired = () => {
      logout();
    };

    window.addEventListener('investiga:session-expired', handleSessionExpired);
    return () => {
      isMounted = false;
      window.removeEventListener('investiga:session-expired', handleSessionExpired);
    };
  }, [setUser, setLoading, logout]);

  return (
    <AuthContext.Provider value={{ isLoading, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = () => useContext(AuthContext);
