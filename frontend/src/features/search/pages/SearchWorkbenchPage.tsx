import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSearch, Sparkles, BookOpen, ArrowRight } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

export const SearchWorkbenchPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border/40">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl flex items-center gap-2">
              <FileSearch className="h-6 w-6 text-cyan-400" />
              Hybrid Search Workbench
            </h1>
            <Badge variant="cyan" className="font-mono text-[10px]">
              ARCHITECTURE SHELL
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Multi-modal retrieval pipeline combining dense vector embeddings and BM25 sparse keyword scoring.
          </p>
        </div>
      </div>

      {/* Domain Shell Notice */}
      <Card className="border-cyan-500/30 bg-cyan-950/10">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/30 flex-shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base">Search Pipeline Endpoint Under Active Staging</CardTitle>
              <CardDescription className="text-xs">
                The hybrid search controller is defined in the backend architecture and awaits endpoint registration in the next release.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 text-xs text-muted-foreground">
          <p>
            In the current phase, you can manage and ingest source runbooks and incident post-mortems via the{' '}
            <strong className="text-foreground">Knowledge Base</strong>, where metadata and SHA-256 cryptographic checksums are indexed in real time.
          </p>
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/knowledge')}
              leftIcon={<BookOpen className="h-3.5 w-3.5" />}
              rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              Browse Knowledge Documents
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Planned Pipeline Blueprint Architecture */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            01
          </div>
          <h3 className="text-sm font-semibold text-foreground">Dense Embedding Model</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Vector representations derived using MiniLM / BGE sentence transformers for semantic query alignment.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            02
          </div>
          <h3 className="text-sm font-semibold text-foreground">BM25 Keyword Scoring</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Exact match indexing for technical identifiers, error codes, HTTP status codes, and exception stack traces.
          </p>
        </Card>

        <Card className="p-5 space-y-2">
          <div className="h-8 w-8 rounded bg-muted/60 text-foreground flex items-center justify-center font-mono text-xs font-bold">
            03
          </div>
          <h3 className="text-sm font-semibold text-foreground">Reciprocal Rank Fusion (RRF)</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Non-linear fusion weighing semantic relevance and exact keyword precision for incident resolution.
          </p>
        </Card>
      </div>
    </div>
  );
};
