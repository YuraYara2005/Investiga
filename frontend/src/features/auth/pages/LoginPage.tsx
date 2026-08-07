import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Lock, Mail, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { authService } from '@/services/authService';
import { tokenStorage } from '@/auth/tokenStorage';
import { useAuthStore } from '@/stores/useAuthStore';
import { toast } from '@/stores/useNotificationStore';
import { parseApiError } from '@/lib/error';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FormField } from '@/components/forms/FormField';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const setSession = useAuthStore((state) => state.setSession);
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormValues) => {
    setIsLoading(true);
    try {
      console.log('LOGIN START');

      // 1. Authenticate with backend /api/v1/auth/login
      const tokenData = await authService.login({
        email: data.email,
        password: data.password,
      });

      console.log('LOGIN RESPONSE', tokenData);

      tokenStorage.setTokens(
        tokenData.access_token,
        tokenData.refresh_token
      );

      console.log(
        'AFTER setTokens',
        localStorage.getItem('investiga_access_token')
      );

      // 2. Fetch authenticated user profile and permissions
      const currentUser = await authService.getCurrentUser();

      console.log('CURRENT USER', currentUser);

      // 3. Persist session
      setSession(currentUser, tokenData.access_token, tokenData.refresh_token);

      console.log('SESSION CREATED');

      toast.success('Welcome back', `Signed in as ${currentUser.full_name || currentUser.email}`);
      navigate(from, { replace: true });
    } catch (err) {
      console.error('LOGIN ERROR', err);
      const parsed = parseApiError(err);
      toast.error('Authentication Failed', parsed.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="border-border/80 bg-card/90 shadow-xl backdrop-blur-md">
      <CardHeader className="space-y-1">
        <CardTitle className="text-xl font-bold tracking-tight">Sign In to Investiga</CardTitle>
        <CardDescription>
          Enter your authorized enterprise credentials to access the incident intelligence suite.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            label="Email Address"
            error={errors.email?.message}
            required
            htmlFor="email"
          >
            <Input
              id="email"
              type="email"
              placeholder="operator@enterprise.com"
              leftIcon={<Mail className="h-4 w-4" />}
              autoComplete="email"
              disabled={isLoading}
              {...register('email')}
            />
          </FormField>

          <FormField
            label="Password"
            error={errors.password?.message}
            required
            htmlFor="password"
          >
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••••••"
              leftIcon={<Lock className="h-4 w-4" />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-muted-foreground hover:text-foreground focus:outline-none p-1"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              autoComplete="current-password"
              disabled={isLoading}
              {...register('password')}
            />
          </FormField>

          <div className="flex items-center justify-between text-xs pt-1">
            <span className="text-muted-foreground">Secured with Argon2id</span>
            <Link
              to="/forgot-password"
              className="text-primary hover:underline font-medium"
            >
              Reset credentials?
            </Link>
          </div>

          <Button
            type="submit"
            variant="primary"
            className="w-full mt-2"
            isLoading={isLoading}
            rightIcon={<ArrowRight className="h-4 w-4" />}
          >
            Authenticate & Proceed
          </Button>

          <div className="text-center text-xs text-muted-foreground pt-3">
            <span>Don't have an operator identity? </span>
            <Link to="/register" className="text-primary hover:underline font-medium">
              Register an account
            </Link>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};
