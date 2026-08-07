import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, Sparkles, BookOpen, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

export const ChatAssistantPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
              <Bot className="h-6 w-6 text-indigo-400" />
              AI Incident Investigation Assistant
            </h1>
            <Badge variant="default" className="font-mono text-[10px]">
              ARCHITECTURE SHELL
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Multi-turn contextual reasoning and RAG assistance across ingested incident runbooks and cluster telemetry.
          </p>
        </div>
      </div>

      {/* Domain Shell Notice */}
      <Card className="border-indigo-500/30 bg-indigo-950/10">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/30 flex-shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">RAG Reasoning Engine Staging</CardTitle>
              <CardDescription className="text-xs">
                The conversational LLM pipeline and streaming endpoint contract are scheduled for rollout in the next phase.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground">
          <p>
            The assistant will generate grounded answers with verifiable citations linking back to ingested runbook sections and post-mortems in the{' '}
            <strong className="text-foreground">Knowledge Base</strong>.
          </p>
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/knowledge')}
              leftIcon={<BookOpen className="h-3.5 w-3.5" />}
              rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Prepare Knowledge Base
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Core Architectural Capabilities */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            01
          </div>
          <h3 className="text-sm font-semibold text-foreground">Strict Groundedness</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Zero hallucination tolerance: responses are synthesized strictly from validated runbook context chunks.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            02
          </div>
          <h3 className="text-sm font-semibold text-foreground">Interactive Citations</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Direct deep-links to document SHA-256 hashes and specific runbook step IDs for operational auditability.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            03
          </div>
          <h3 className="text-sm font-semibold text-foreground">Enterprise Guardrails</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Adversarial prompt injection defense, credential sanitization, and strict RBAC authorization filtering.
          </p>
        </Card>
      </div>
    </div>
  );
};
