import apiClient from '@/api/client';
import type { HealthResponse, LivenessResponse, ReadinessResponse } from '@/types/health';

/**
 * Platform Diagnostic and Health Probe Service communicating with `/health/*`.
 */
export const healthService = {
  /**
   * Comprehensive health check with subsystem latencies.
   */
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
  },

  /**
   * Lightweight Kubernetes liveness probe.
   */
  async getLiveness(): Promise<LivenessResponse> {
    const response = await apiClient.get<LivenessResponse>('/health/live');
    return response.data;
  },

  /**
   * Kubernetes readiness probe with critical dependency checks.
   */
  async getReadiness(): Promise<ReadinessResponse> {
    const response = await apiClient.get<ReadinessResponse>('/health/ready');
    return response.data;
  },
};
