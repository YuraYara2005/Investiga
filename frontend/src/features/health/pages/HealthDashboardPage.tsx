import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  RefreshCw,
  Server,
  ShieldCheck,
  Zap,
  Terminal,
} from 'lucide-react';
import { healthService } from '@/services/healthService';
import { queryKeys } from '@/api/queryKeys';
import { formatLatency } from '@/lib/utils';
import { formatDate } from '@/lib/date';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { HealthStatusBadge } from '@/components/ui/StatusBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { CodeBlock } from '@/components/data/CodeBlock';
import { Tabs } from '@/components/ui/Tabs';

export const HealthDashboardPage: React.FC = () => {
  const [refreshInterval, setRefreshInterval] = useState<number>(10000); // 10s default
  const [activeTab, setActiveTab] = useState<string>('subsystems');

  // Comprehensive health probe
  const {
    data: health,
    isLoading: isLoadingHealth,
    isFetching: isFetchingHealth,
    refetch: refetchHealth,
    dataUpdatedAt,
  } = useQuery({
    queryKey: queryKeys.health.full(),
    queryFn: () => healthService.getHealth(),
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
  });

  // Liveness probe
  const { data: liveness, refetch: refetchLiveness } = useQuery({
    queryKey: queryKeys.health.live(),
    queryFn: () => healthService.getLiveness(),
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
  });

  // Readiness probe
  const { data: readiness, refetch: refetchReadiness } = useQuery({
    queryKey: queryKeys.health.ready(),
    queryFn: () => healthService.getReadiness(),
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
  });

  const handleRefreshAll = () => {
    refetchHealth();
    refetchLiveness();
    refetchReadiness();
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
            <Activity className="h-6 w-6 text-emerald-400" />
            System Health & Diagnostics
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time cluster telemetry, Kubernetes liveness/readiness probes, and dependency status.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Refresh Interval Selector */}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Poll:</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="bg-card border border-border/80 rounded px-2 py-1 text-xs text-foreground cursor-pointer"
            >
              <option value={5000}>5 sec</option>
              <option value={10000}>10 sec</option>
              <option value={30000}>30 sec</option>
              <option value={0}>Manual</option>
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            isLoading={isFetchingHealth}
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            Run Probes
          </Button>
        </div>
      </div>

      {/* Top Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Overall Cluster Status
              </p>
              <div className="text-xl font-bold mt-1 text-foreground">
                {isLoadingHealth ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  <span className="capitalize">{health?.status || 'Unknown'}</span>
                )}
              </div>
            </div>
            {health?.status && <HealthStatusBadge status={health.status} />}
          </div>
          <p className="text-[11px] text-muted-foreground mt-3 font-mono">
            Last probe:{' '}
            {dataUpdatedAt ? formatDate(new Date(dataUpdatedAt), 'HH:mm:ss') : '—'}
          </p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Kubernetes Liveness
              </p>
              <div className="text-xl font-bold mt-1 text-foreground font-mono">
                {liveness?.status === 'alive' ? (
                  <span className="text-emerald-400">ALIVE</span>
                ) : (
                  'UNKNOWN'
                )}
              </div>
            </div>
            <div className="h-8 w-8 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <Zap className="h-4 w-4" />
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-3 font-mono">
            Probe: /health/live
          </p>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Kubernetes Readiness
              </p>
              <div className="text-xl font-bold mt-1 text-foreground font-mono">
                {readiness?.status === 'ready' ? (
                  <span className="text-emerald-400">READY</span>
                ) : (
                  'NOT READY'
                )}
              </div>
            </div>
            <div className="h-8 w-8 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-3 font-mono">
            Probe: /health/ready
          </p>
        </Card>
      </div>

      {/* Tabs: Subsystems vs Raw Probe Data */}
      <Tabs
        tabs={[
          { id: 'subsystems', label: 'Component Health & Latency', icon: <Server className="h-3.5 w-3.5" /> },
          { id: 'raw', label: 'Raw Probe Responses (JSON)', icon: <Terminal className="h-3.5 w-3.5" /> },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'subsystems' ? (
        <Card>
          <CardHeader>
            <CardTitle>Subsystem Health Diagnostics</CardTitle>
            <CardDescription>
              Environment: <strong className="font-mono text-foreground">{health?.environment || 'development'}</strong> • Application: <strong className="font-mono text-foreground">{health?.application || 'investiga'}</strong> • Version: <strong className="font-mono text-foreground">{health?.version || '1.0.0'}</strong>
            </CardDescription>
          </CardHeader>

          <CardContent>
            {isLoadingHealth ? (
              <div className="space-y-3">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : health?.components && Object.keys(health.components).length > 0 ? (
              <div className="divide-y divide-border/40">
                {Object.entries(health.components).map(([name, comp]) => (
                  <div
                    key={name}
                    className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-foreground capitalize">
                          {name}
                        </span>
                        <HealthStatusBadge status={comp.status} />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {comp.details || 'Component responding normally to automated diagnostic probes'}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 text-xs font-mono">
                      <div className="text-right">
                        <span className="text-[10px] text-muted-foreground uppercase block">
                          Response Latency
                        </span>
                        <span className="font-bold text-foreground">
                          {formatLatency(comp.latency_ms)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-muted-foreground">
                No individual subsystem probes defined on this cluster. Core HTTP stack is operational.
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              GET /health
            </h3>
            <CodeBlock code={JSON.stringify(health || {}, null, 2)} language="json" />
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              GET /health/ready
            </h3>
            <CodeBlock code={JSON.stringify(readiness || {}, null, 2)} language="json" />
          </div>
        </div>
      )}
    </div>
  );
};
