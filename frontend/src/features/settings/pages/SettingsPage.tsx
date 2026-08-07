import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  User,
  Lock,
  Shield,
  KeyRound,
  Eye,
  EyeOff,
  CheckCircle2,
} from 'lucide-react';
import { authService } from '@/services/authService';
import { queryKeys } from '@/api/queryKeys';
import { useAuth } from '@/auth/useAuth';
import { useAuthStore } from '@/stores/useAuthStore';
import { toast } from '@/stores/useNotificationStore';
import { parseApiError } from '@/lib/error';
import { formatDate } from '@/lib/date';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FormField } from '@/components/forms/FormField';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Tabs } from '@/components/ui/Tabs';

// Profile form schema
const profileSchema = z.object({
  fullName: z.string().min(2, 'Full name must be at least 2 characters'),
});
type ProfileFormValues = z.infer<typeof profileSchema>;

// Password change schema
const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: z
      .string()
      .min(8, 'New password must be at least 8 characters')
      .regex(/[A-Z]/, 'Must contain at least one uppercase letter')
      .regex(/[0-9]/, 'Must contain at least one number'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });
type PasswordFormValues = z.infer<typeof passwordSchema>;

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<string>('profile');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const queryClient = useQueryClient();

  // Profile Form
  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    formState: { errors: profileErrors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      fullName: user?.full_name || '',
    },
  });

  // Password Form
  const {
    register: registerPassword,
    handleSubmit: handleSubmitPassword,
    reset: resetPassword,
    formState: { errors: passwordErrors },
  } = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  });

  // Profile mutation
  const profileMutation = useMutation({
    mutationFn: (data: ProfileFormValues) =>
      authService.updateProfile({ full_name: data.fullName }),
    onSuccess: (updated) => {
      toast.success('Profile Updated', 'Your identity name has been saved.');
      // Refresh current user in store & cache
      if (user) {
        useAuthStore.getState().setUser({
          ...user,
          full_name: updated.full_name,
        });
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.currentUser() });
    },
    onError: (err) => {
      const parsed = parseApiError(err);
      toast.error('Update Failed', parsed.message);
    },
  });

  // Password mutation
  const passwordMutation = useMutation({
    mutationFn: (data: PasswordFormValues) =>
      authService.changePassword({
        current_password: data.currentPassword,
        new_password: data.newPassword,
      }),
    onSuccess: () => {
      toast.success('Password Changed', 'Your security password was rotated successfully.');
      resetPassword();
    },
    onError: (err) => {
      const parsed = parseApiError(err);
      toast.error('Password Update Failed', parsed.message);
    },
  });

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="pb-2 border-b border-border/40">
        <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
          Account & Security Settings
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Manage your operator identity, security credentials, and view RBAC entitlements.
        </p>
      </div>

      <Tabs
        tabs={[
          { id: 'profile', label: 'Operator Profile', icon: <User className="h-3.5 w-3.5" /> },
          { id: 'security', label: 'Security & Password', icon: <Lock className="h-3.5 w-3.5" /> },
          { id: 'rbac', label: 'Assigned Entitlements', icon: <Shield className="h-3.5 w-3.5" /> },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />

      {/* Tab 1: Profile */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile Details</CardTitle>
              <CardDescription>
                Your personal identity attributes across the Investiga cluster.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <form
                onSubmit={handleSubmitProfile((data) => profileMutation.mutate(data))}
                className="space-y-4 max-w-md"
              >
                <FormField
                  label="Full Name"
                  error={profileErrors.fullName?.message}
                  required
                  htmlFor="profile-name"
                >
                  <Input
                    id="profile-name"
                    disabled={profileMutation.isPending}
                    {...registerProfile('fullName')}
                  />
                </FormField>

                <FormField
                  label="Email Address"
                  helperText="Primary email cannot be changed without administrator approval"
                  htmlFor="profile-email"
                >
                  <Input
                    id="profile-email"
                    value={user?.email || ''}
                    disabled
                    className="bg-muted/50 cursor-not-allowed font-mono text-xs"
                  />
                </FormField>

                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    isLoading={profileMutation.isPending}
                  >
                    Save Profile Changes
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Account Metadata Card */}
          <Card className="p-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Account Registration Telemetry
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
              <div>
                <span className="text-muted-foreground text-[10px] block">OPERATOR ID</span>
                <span className="font-semibold text-foreground truncate block">{user?.id}</span>
              </div>
              <div>
                <span className="text-muted-foreground text-[10px] block">JOINED DATE</span>
                <span className="font-semibold text-foreground">
                  {formatDate(user?.created_at, 'MMM dd, yyyy')}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground text-[10px] block">LAST LOGIN</span>
                <span className="font-semibold text-foreground">
                  {user?.last_login_at ? formatDate(user.last_login_at) : 'Active Session'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Tab 2: Security & Password */}
      {activeTab === 'security' && (
        <Card>
          <CardHeader>
            <CardTitle>Rotate Security Password</CardTitle>
            <CardDescription>
              Update your account password with Argon2id cryptographic hashing.
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form
              onSubmit={handleSubmitPassword((data) => passwordMutation.mutate(data))}
              className="space-y-4 max-w-md"
            >
              <FormField
                label="Current Password"
                error={passwordErrors.currentPassword?.message}
                required
                htmlFor="curr-pass"
              >
                <Input
                  id="curr-pass"
                  type={showCurrentPassword ? 'text' : 'password'}
                  leftIcon={<KeyRound className="h-4 w-4" />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                      className="text-muted-foreground hover:text-foreground p-1"
                      tabIndex={-1}
                    >
                      {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                  disabled={passwordMutation.isPending}
                  {...registerPassword('currentPassword')}
                />
              </FormField>

              <FormField
                label="New Password"
                error={passwordErrors.newPassword?.message}
                required
                htmlFor="new-pass"
                helperText="Must be at least 8 chars, 1 uppercase letter, 1 number"
              >
                <Input
                  id="new-pass"
                  type={showNewPassword ? 'text' : 'password'}
                  leftIcon={<Lock className="h-4 w-4" />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="text-muted-foreground hover:text-foreground p-1"
                      tabIndex={-1}
                    >
                      {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                  disabled={passwordMutation.isPending}
                  {...registerPassword('newPassword')}
                />
              </FormField>

              <FormField
                label="Confirm New Password"
                error={passwordErrors.confirmPassword?.message}
                required
                htmlFor="confirm-pass"
              >
                <Input
                  id="confirm-pass"
                  type={showNewPassword ? 'text' : 'password'}
                  leftIcon={<Shield className="h-4 w-4" />}
                  disabled={passwordMutation.isPending}
                  {...registerPassword('confirmPassword')}
                />
              </FormField>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={passwordMutation.isPending}
                >
                  Update Password
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Tab 3: RBAC Claims */}
      {activeTab === 'rbac' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Assigned Roles & Superuser Status</CardTitle>
              <CardDescription>
                System roles determine access rights across cluster endpoints and operations.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                {user?.is_superuser && (
                  <Badge variant="destructive" className="font-mono text-xs">
                    ★ SUPERUSER (FULL CLUSTER ACCESS)
                  </Badge>
                )}
                {user?.roles?.map((role) => (
                  <Badge key={role} variant="cyan" className="font-mono text-xs">
                    ROLE: {role}
                  </Badge>
                ))}
              </div>

              <div className="p-4 rounded-lg bg-muted/30 border border-border/60 text-xs text-muted-foreground leading-relaxed">
                Superusers inherit all permissions implicitly. For other roles, permissions are resolved additively from assigned role definitions.
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Effective Permission Claims ({user?.permissions?.length || 0})</CardTitle>
              <CardDescription>
                Granular action entitlements granted to this identity token.
              </CardDescription>
            </CardHeader>

            <CardContent>
              {user?.permissions && user.permissions.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {user.permissions.map((perm) => (
                    <div
                      key={perm}
                      className="p-2.5 rounded border border-border/60 bg-card font-mono text-[11px] text-foreground flex items-center gap-2"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 flex-shrink-0" />
                      <span className="truncate">{perm}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {user?.is_superuser
                    ? 'Superuser grants wildcard access (*:*) across all resources.'
                    : 'No specific individual permissions assigned.'}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
