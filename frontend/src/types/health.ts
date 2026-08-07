export type ComponentStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ComponentHealth {
  status: ComponentStatus;
  latency_ms: number | null;
  details?: string | null;
}

export interface HealthResponse {
  status: ComponentStatus;
  application: string;
  version: string;
  environment: string;
  timestamp: string;
  components: Record<string, ComponentHealth>;
}

export interface LivenessResponse {
  status: 'alive';
  timestamp: string;
}

export interface ReadinessResponse {
  status: 'ready';
  timestamp: string;
  components: Record<string, ComponentHealth>;
}
