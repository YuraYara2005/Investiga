import type { DocumentQueryParams } from '@/types/knowledge';

/**
 * Centralized Query Key factory for TanStack Query.
 * Guarantees consistent cache management and selective cache invalidation.
 */
export const queryKeys = {
  auth: {
    all: ['auth'] as const,
    currentUser: () => [...queryKeys.auth.all, 'current-user'] as const,
  },
  health: {
    all: ['health'] as const,
    live: () => [...queryKeys.health.all, 'live'] as const,
    ready: () => [...queryKeys.health.all, 'ready'] as const,
    full: () => [...queryKeys.health.all, 'full'] as const,
  },
  knowledge: {
    all: ['knowledge'] as const,
    lists: () => [...queryKeys.knowledge.all, 'list'] as const,
    list: (params?: DocumentQueryParams) => [...queryKeys.knowledge.lists(), params ?? {}] as const,
    details: () => [...queryKeys.knowledge.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.knowledge.details(), id] as const,
  },
} as const;
