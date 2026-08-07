import React from 'react';
import { useAuth } from './useAuth';

interface PermissionGuardProps {
  permission?: string;
  role?: string;
  requireSuperuser?: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Granular RBAC permission check component.
 * Conditionally renders children if the authenticated user possesses the required authorization entitlement.
 */
export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  permission,
  role,
  requireSuperuser = false,
  fallback = null,
  children,
}) => {
  const { isSuperuser, hasPermission, hasRole } = useAuth();

  if (requireSuperuser && !isSuperuser) {
    return <>{fallback}</>;
  }

  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  if (role && !hasRole(role)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};
