import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/useAuth';
import { LoadingScreen } from '@/components/feedback/LoadingScreen';

interface ProtectedRouteProps {
  requiredPermission?: string;
  requiredRole?: string;
  requireSuperuser?: boolean;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  requiredPermission,
  requiredRole,
  requireSuperuser = false,
}) => {
  const { isAuthenticated, isLoading, isSuperuser, hasPermission, hasRole } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <LoadingScreen label="Verifying session credentials..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireSuperuser && !isSuperuser) {
    return <Navigate to="/403" replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission) && !isSuperuser) {
    return <Navigate to="/403" replace />;
  }

  if (requiredRole && !hasRole(requiredRole) && !isSuperuser) {
    return <Navigate to="/403" replace />;
  }

  return <Outlet />;
};
