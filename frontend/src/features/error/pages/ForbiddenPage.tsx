import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldX, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export const ForbiddenPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="h-16 w-16 rounded-2xl bg-destructive/10 border border-destructive/30 text-destructive flex items-center justify-center mb-6 shadow-lg shadow-destructive/10">
        <ShieldX className="h-8 w-8" />
      </div>

      <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-destructive/10 text-destructive border border-destructive/20 mb-3">
        HTTP 403 // INSUFFICIENT_PERMISSIONS
      </span>

      <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
        Access Restricted by Policy
      </h1>

      <p className="text-xs sm:text-sm text-muted-foreground max-w-md mt-2 mb-8 leading-relaxed">
        Your current operator role does not possess the required RBAC entitlement to access this endpoint or cluster domain.
      </p>

      <Link to="/dashboard">
        <Button variant="primary" leftIcon={<ArrowLeft className="h-4 w-4" />}>
          Return to Dashboard
        </Button>
      </Link>
    </div>
  );
};
