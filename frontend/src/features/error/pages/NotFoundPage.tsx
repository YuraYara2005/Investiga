import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="h-16 w-16 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/10">
        <Compass className="h-8 w-8" />
      </div>

      <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-muted text-muted-foreground border border-border/60 mb-3">
        HTTP 404 // RESOURCE_NOT_FOUND
      </span>

      <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
        Page or Resource Not Found
      </h1>

      <p className="text-xs sm:text-sm text-muted-foreground max-w-md mt-2 mb-8 leading-relaxed">
        The requested path does not exist on this cluster or you may have followed an expired link.
      </p>

      <Link to="/dashboard">
        <Button variant="primary" leftIcon={<ArrowLeft className="h-4 w-4" />}>
          Return to Dashboard
        </Button>
      </Link>
    </div>
  );
};
