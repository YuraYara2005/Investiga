import React, { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/layouts/AppLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { ProtectedRoute } from './ProtectedRoute';
import { LoadingScreen } from '@/components/feedback/LoadingScreen';

// Lazy-loaded feature routes for code splitting
const DashboardPage = lazy(() =>
  import('@/features/dashboard/pages/DashboardPage').then((m) => ({
    default: m.DashboardPage,
  }))
);
const KnowledgeListPage = lazy(() =>
  import('@/features/knowledge/pages/KnowledgeListPage').then((m) => ({
    default: m.KnowledgeListPage,
  }))
);
const HealthDashboardPage = lazy(() =>
  import('@/features/health/pages/HealthDashboardPage').then((m) => ({
    default: m.HealthDashboardPage,
  }))
);
const SettingsPage = lazy(() =>
  import('@/features/settings/pages/SettingsPage').then((m) => ({
    default: m.SettingsPage,
  }))
);
const RolesMatrixPage = lazy(() =>
  import('@/features/admin/pages/RolesMatrixPage').then((m) => ({
    default: m.RolesMatrixPage,
  }))
);
const SearchWorkbenchPage = lazy(() =>
  import('@/features/search/pages/SearchWorkbenchPage').then((m) => ({
    default: m.SearchWorkbenchPage,
  }))
);
const ChatAssistantPage = lazy(() =>
  import('@/features/chat/pages/ChatAssistantPage').then((m) => ({
    default: m.ChatAssistantPage,
  }))
);
const EvaluationPage = lazy(() =>
  import('@/features/evaluation/pages/EvaluationPage').then((m) => ({
    default: m.EvaluationPage,
  }))
);
const LoginPage = lazy(() =>
  import('@/features/auth/pages/LoginPage').then((m) => ({
    default: m.LoginPage,
  }))
);
const RegisterPage = lazy(() =>
  import('@/features/auth/pages/RegisterPage').then((m) => ({
    default: m.RegisterPage,
  }))
);
const ForgotPasswordPage = lazy(() =>
  import('@/features/auth/pages/ForgotPasswordPage').then((m) => ({
    default: m.ForgotPasswordPage,
  }))
);
const NotFoundPage = lazy(() =>
  import('@/features/error/pages/NotFoundPage').then((m) => ({
    default: m.NotFoundPage,
  }))
);
const ForbiddenPage = lazy(() =>
  import('@/features/error/pages/ForbiddenPage').then((m) => ({
    default: m.ForbiddenPage,
  }))
);

const SuspenseWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense fallback={<LoadingScreen label="Loading view component..." />}>
    {children}
  </Suspense>
);

export const router = createBrowserRouter([
  // Public Authentication Routes
  {
    element: <AuthLayout />,
    children: [
      {
        path: '/login',
        element: (
          <SuspenseWrapper>
            <LoginPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: '/register',
        element: (
          <SuspenseWrapper>
            <RegisterPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: '/forgot-password',
        element: (
          <SuspenseWrapper>
            <ForgotPasswordPage />
          </SuspenseWrapper>
        ),
      },
    ],
  },

  // Protected Application Routes
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          {
            path: '/',
            element: <Navigate to="/dashboard" replace />,
          },
          {
            path: '/dashboard',
            element: (
              <SuspenseWrapper>
                <DashboardPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/knowledge',
            element: (
              <SuspenseWrapper>
                <KnowledgeListPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/search',
            element: (
              <SuspenseWrapper>
                <SearchWorkbenchPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/chat',
            element: (
              <SuspenseWrapper>
                <ChatAssistantPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/evaluation',
            element: (
              <SuspenseWrapper>
                <EvaluationPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/admin/health',
            element: (
              <SuspenseWrapper>
                <HealthDashboardPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/admin/roles',
            element: (
              <SuspenseWrapper>
                <RolesMatrixPage />
              </SuspenseWrapper>
            ),
          },
          {
            path: '/settings',
            element: (
              <SuspenseWrapper>
                <SettingsPage />
              </SuspenseWrapper>
            ),
          },
        ],
      },
    ],
  },

  // Static Error Routes
  {
    path: '/403',
    element: (
      <SuspenseWrapper>
        <ForbiddenPage />
      </SuspenseWrapper>
    ),
  },
  {
    path: '*',
    element: (
      <SuspenseWrapper>
        <NotFoundPage />
      </SuspenseWrapper>
    ),
  },
]);
