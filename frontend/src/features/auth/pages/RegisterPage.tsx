import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Mail, User, ArrowRight, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { authService } from '@/services/authService';
import { toast } from '@/stores/useNotificationStore';
import { parseApiError } from '@/lib/error';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FormField } from '@/components/forms/FormField';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';

const registerSchema = z
  .object({
    fullName: z.string().min(2, 'Full name must be at least 2 characters'),
    email: z.string().email('Please enter a valid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export const RegisterPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      fullName: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setIsLoading(true);
    try {
      await authService.register({
        email: data.email,
        password: data.password,
        full_name: data.fullName,
      });

      toast.success(
        'Registration Successful',
        'Your operator account has been created. Please sign in.'
      );
      navigate('/login');
    } catch (err) {
      const parsed = parseApiError(err);
      toast.error('Registration Failed', parsed.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="border-border/80 bg-card/90 shadow-xl backdrop-blur-md">
      <CardHeader className="space-y-1">
        <CardTitle className="text-xl font-bold tracking-tight">Create Operator Account</CardTitle>
        <CardDescription>
          Register an enterprise profile to authenticate and collaborate in incident response.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            label="Full Name"
            error={errors.fullName?.message}
            required
            htmlFor="fullName"
          >
            <Input
              id="fullName"
              placeholder="Alex Vance"
              leftIcon={<User className="h-4 w-4" />}
              autoComplete="name"
              disabled={isLoading}
              {...register('fullName')}
            />
          </FormField>

          <FormField
            label="Work Email Address"
            error={errors.email?.message}
            required
            htmlFor="email"
          >
            <Input
              id="email"
              type="email"
              placeholder="alex.vance@enterprise.com"
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
            helperText="At least 8 chars, 1 uppercase letter, 1 number"
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
              autoComplete="new-password"
              disabled={isLoading}
              {...register('password')}
            />
          </FormField>

          <FormField
            label="Confirm Password"
            error={errors.confirmPassword?.message}
            required
            htmlFor="confirmPassword"
          >
            <Input
              id="confirmPassword"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••••••"
              leftIcon={<ShieldCheck className="h-4 w-4" />}
              autoComplete="new-password"
              disabled={isLoading}
              {...register('confirmPassword')}
            />
          </FormField>

          <Button
            type="submit"
            variant="primary"
            className="w-full mt-2"
            isLoading={isLoading}
            rightIcon={<ArrowRight className="h-4 w-4" />}
          >
            Register Operator Profile
          </Button>

          <div className="text-center text-xs text-muted-foreground pt-3">
            <span>Already registered? </span>
            <Link to="/login" className="text-primary hover:underline font-medium">
              Sign in to your account
            </Link>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};
