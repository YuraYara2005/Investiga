import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  BookOpen,
  UploadCloud,
  FileSearch,
  Bot,
  Activity,
  ShieldCheck,
  ArrowRight,
  RefreshCw,
  Cpu,
  Layers,
} from 'lucide-react';
import { knowledgeService } from '@/services/knowledgeService';
import { healthService } from '@/services/healthService';
import { queryKeys } from '@/api/queryKeys';
import { useAuth } from '@/auth/useAuth';
import { MetricCard } from '@/components/data/MetricCard';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { HealthStatusBadge } from '@/components/ui/StatusBadge';
import { formatBytes, formatLatency } from '@/lib/utils';
import { formatDate } from '@/lib/date';
import { Skeleton } from '@/components/ui/Skeleton';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Fetch real document list summary
  const {
    data: docsData,
    isLoading: isLoadingDocs,
    refetch: refetchDocs,
  } = useQuery({
    queryKey: queryKeys.knowledge.list({ limit: 5 }),
    queryFn: () => knowledgeService.listDocuments({ limit: 5 }),
  });

  // Fetch real platform health
  const {
    data: healthData,
    isLoading: isLoadingHealth,
    refetch: refetchHealth,
    isFetching: isFetchingHealth,
  } = useQuery({
    queryKey: queryKeys.health.full(),
    queryFn: () => healthService.getHealth(),
    refetchInterval: 30000,
  });

  const totalBytes =
    docsData?.items?.reduce((acc, item) => acc + (item.file_size || 0), 0) ?? 0;

  const handleRefreshAll = () => {
    refetchDocs();
    refetchHealth();
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
            Incident Operations Center
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Logged in as <span className="font-semibold text-foreground">{user?.full_name}</span>{' '}
            (<span className="font-mono text-cyan-400">{user?.roles?.[0] || 'Operator'}</span>)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            isLoading={isFetchingHealth}
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            Refresh Telemetry
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/knowledge?action=upload')}
            leftIcon={<UploadCloud className="h-3.5 w-3.5" />}
          >
            Upload Document
          </Button>
        </div>
      </div>

      {/* Top Metric Cards (Real backend telemetry) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Indexed Runbooks"
          value={isLoadingDocs ? <Skeleton className="h-8 w-16" /> : docsData?.total ?? 0}
          subtitle="Active operational documents"
          icon={<BookOpen className="h-5 w-5 text-indigo-400" />}
        />

        <MetricCard
          title="Ingested Volume"
          value={isLoadingDocs ? <Skeleton className="h-8 w-24" /> : formatBytes(totalBytes)}
          subtitle="Total document payload"
          icon={<Layers className="h-5 w-5 text-cyan-400" />}
        />

        <MetricCard
          title="Cluster Health"
          value={
            isLoadingHealth ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <span className="capitalize">{healthData?.status ?? 'Unknown'}</span>
            )
          }
          subtitle={healthData?.environment ? `Env: ${healthData.environment}` : 'Active cluster status'}
          badge={healthData?.status ? <HealthStatusBadge status={healthData.status} /> : undefined}
          icon={<Activity className="h-5 w-5 text-emerald-400" />}
        />

        <MetricCard
          title="Engine Version"
          value={isLoadingHealth ? <Skeleton className="h-8 w-20" /> : healthData?.version || '1.0.0'}
          subtitle={healthData?.application || 'Investiga API'}
          icon={<Cpu className="h-5 w-5 text-amber-400" />}
        />
      </div>

      {/* Main Grid: Subsystems Health & Quick Navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Subsystem Health Status */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle>Core Infrastructure Health</CardTitle>
              <CardDescription>Live telemetry from cluster dependency probes</CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/admin/health')}
              rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Diagnostic View
            </Button>
          </CardHeader>

          <CardContent>
            {isLoadingHealth ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : healthData?.components && Object.keys(healthData.components).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(healthData.components).map(([name, probe]) => (
                  <div
                    key={name}
                    className="flex items-center justify-between p-3 rounded-lg border border-border/60 bg-muted/20 text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded bg-card border border-border/60 flex items-center justify-center font-mono font-bold text-foreground">
                        {name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-semibold text-foreground capitalize">{name}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {probe.details || 'Component probe responding'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-muted-foreground">
                        {formatLatency(probe.latency_ms)}
                      </span>
                      <HealthStatusBadge status={probe.status} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-muted/30 border border-border/40 text-xs text-muted-foreground text-center">
                No individual component probes reported. Root API is operational.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Launchpad */}
        <Card>
          <CardHeader>
            <CardTitle>Investigation Launchpad</CardTitle>
            <CardDescription>Access intelligence pipelines and diagnostic tools</CardDescription>
          </CardHeader>

          <CardContent className="space-y-2.5">
            <button
              onClick={() => navigate('/knowledge')}
              className="w-full flex items-center justify-between p-3 rounded-lg border border-border/60 bg-card hover:bg-accent hover:border-primary/40 transition-colors text-left group"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
                  <BookOpen className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors">
                    Knowledge Base
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Browse and upload operational runbooks
                  </p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-transform group-hover:translate-x-0.5" />
            </button>

            <button
              onClick={() => navigate('/search')}
              className="w-full flex items-center justify-between p-3 rounded-lg border border-border/60 bg-card hover:bg-accent hover:border-cyan-400/40 transition-colors text-left group"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                  <FileSearch className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground group-hover:text-cyan-400 transition-colors">
                    Search Workbench
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Query documents with hybrid search
                  </p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-cyan-400 transition-transform group-hover:translate-x-0.5" />
            </button>

            <button
              onClick={() => navigate('/chat')}
              className="w-full flex items-center justify-between p-3 rounded-lg border border-border/60 bg-card hover:bg-accent hover:border-indigo-400/40 transition-colors text-left group"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
                  <Bot className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground group-hover:text-indigo-400 transition-colors">
                    AI Assistant (RAG)
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Multi-turn incident reasoning
                  </p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-indigo-400 transition-transform group-hover:translate-x-0.5" />
            </button>

            <button
              onClick={() => navigate('/admin/roles')}
              className="w-full flex items-center justify-between p-3 rounded-lg border border-border/60 bg-card hover:bg-accent hover:border-rose-400/40 transition-colors text-left group"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-rose-500/10 text-rose-400 flex items-center justify-center">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground group-hover:text-rose-400 transition-colors">
                    RBAC Entitlements
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Inspect role and permission matrix
                  </p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-rose-400 transition-transform group-hover:translate-x-0.5" />
            </button>
          </CardContent>
        </Card>
      </div>

      {/* Recent Documents Table (Real API items) */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle>Recent Ingested Documents</CardTitle>
            <CardDescription>Latest knowledge items processed by the pipeline</CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/knowledge')}
            rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
          >
            View All Documents
          </Button>
        </CardHeader>

        <CardContent>
          {isLoadingDocs ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !docsData?.items || docsData.items.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              No knowledge documents uploaded yet.{' '}
              <button
                onClick={() => navigate('/knowledge?action=upload')}
                className="text-primary hover:underline font-medium"
              >
                Upload your first incident runbook
              </button>
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {docsData.items.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => navigate(`/knowledge?doc=${doc.id}`)}
                  className="py-3 flex items-center justify-between hover:bg-muted/30 px-2 rounded-lg transition-colors cursor-pointer"
                >
                  <div className="min-w-0 flex-1 pr-4">
                    <p className="text-xs font-semibold text-foreground truncate">{doc.title}</p>
                    <p className="text-[11px] text-muted-foreground truncate mt-0.5 font-mono">
                      {doc.original_filename} • {formatBytes(doc.file_size)} • v{doc.version}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="hidden sm:inline font-mono text-[11px]">
                      {formatDate(doc.created_at, 'MMM dd, HH:mm')}
                    </span>
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-muted/60 text-muted-foreground">
                      {doc.category}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
