import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

export const ForgotPasswordPage: React.FC = () => {
  return (
    <Card className="border-border/80 bg-card/90 shadow-xl backdrop-blur-md">
      <CardHeader className="space-y-1">
        <div className="h-10 w-10 rounded-lg bg-amber-500/10 text-amber-500 flex items-center justify-center mb-2">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <CardTitle className="text-xl font-bold tracking-tight">Credential Recovery</CardTitle>
        <CardDescription>
          Investiga operates on zero-trust enterprise security.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="p-4 rounded-lg bg-muted/40 border border-border/60 text-xs text-muted-foreground space-y-2">
          <p>
            Due to hardware-grade Argon2id encryption policies, self-service password reset is delegated to your organization's Cluster Administrator or Identity Provider.
          </p>
          <p>
            If you are locked out of your account, please reach out to your SRE / Security Operations team or login with your root administrator credentials.
          </p>
        </div>

        <Link to="/login" className="block">
          <Button
            variant="outline"
            className="w-full"
            leftIcon={<ArrowLeft className="h-4 w-4" />}
          >
            Back to Sign In
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
};
