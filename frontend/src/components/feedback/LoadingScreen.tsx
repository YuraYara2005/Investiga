import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingScreen: React.FC<{ label?: string }> = ({
  label = 'Loading Investiga Platform...',
}) => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground p-4">
      <div className="relative flex items-center justify-center">
        <div className="h-14 w-14 rounded-2xl bg-indigo-950/40 border border-cyan-500/30 flex items-center justify-center shadow-lg shadow-cyan-500/10">
          <Loader2 className="h-7 w-7 animate-spin text-cyan-400" />
        </div>
      </div>
      <p className="text-xs font-medium text-muted-foreground tracking-wide mt-4 animate-pulse">
        {label}
      </p>
    </div>
  );
};
