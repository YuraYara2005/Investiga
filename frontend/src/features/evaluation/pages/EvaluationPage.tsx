import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart2, Sparkles, Activity, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

export const EvaluationPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
              <BarChart2 className="h-6 w-6 text-amber-400" />
              Evaluation & Benchmarking
            </h1>
            <Badge variant="warning" className="font-mono text-[10px]">
              ARCHITECTURE SHELL
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Automated evaluation suite for measuring retrieval precision, context recall, and response faithfulness.
          </p>
        </div>
      </div>

      {/* Domain Shell Notice */}
      <Card className="border-amber-500/30 bg-amber-950/10">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/30 flex-shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">Evaluation Suite Orchestration Shell</CardTitle>
              <CardDescription className="text-xs">
                The Python evaluation harness (`backend/app/evaluation`) exists in the backend and will expose interactive REST triggers in an upcoming release.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground">
          <p>
            You can verify current cluster operational readiness and subsystem probe latencies in the{' '}
            <strong className="text-foreground">System Health</strong> dashboard.
          </p>
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/admin/health')}
              leftIcon={<Activity className="h-3.5 w-3.5" />}
              rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Inspect Cluster Health
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Benchmark Metric Criteria */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            01
          </div>
          <h3 className="text-sm font-semibold text-foreground">Context Precision & Recall</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Evaluates whether the retriever ranked ground-truth runbook procedures in top-k positions.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            02
          </div>
          <h3 className="text-sm font-semibold text-foreground">Faithfulness / Hallucination</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Measures mathematical fidelity to verify every claim is directly supported by retrieved context.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            03
          </div>
          <h3 className="text-sm font-semibold text-foreground">Answer Relevance</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Computes semantic embedding alignment between incident query intent and synthesized resolution steps.
          </p>
        </Card>
      </div>
    </div>
  );
};
