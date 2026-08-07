import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Moon,
  Sun,
  User,
  LogOut,
  Shield,
  Menu,
  Activity,
  Sliders,
} from 'lucide-react';
import { useThemeStore } from '@/stores/useThemeStore';
import { useUIStore } from '@/stores/useUIStore';
import { useCommandStore } from '@/stores/useCommandStore';
import { useAuth } from '@/auth/useAuth';
import { DropdownMenu, type DropdownMenuItem } from '@/components/ui/DropdownMenu';
import { Button } from '@/components/ui/Button';

export const TopNav: React.FC = () => {
  const { toggleTheme, effectiveTheme } = useThemeStore();
  const { setMobileNavOpen, isMobileNavOpen } = useUIStore();
  const { setOpen } = useCommandStore();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems: DropdownMenuItem[] = [
    {
      id: 'profile-header',
      label: (
        <div className="flex flex-col py-1">
          <span className="font-semibold text-foreground">{user?.full_name || 'Investiga User'}</span>
          <span className="text-[10px] text-muted-foreground truncate">{user?.email}</span>
        </div>
      ),
      disabled: true,
    },
    {
      id: 'divider-1',
      label: '',
      divider: true,
    },
    {
      id: 'profile-settings',
      label: 'Profile & Security',
      icon: <Sliders className="h-3.5 w-3.5 text-indigo-400" />,
      onClick: () => navigate('/settings'),
    },
    {
      id: 'admin-health',
      label: 'System Diagnostics',
      icon: <Activity className="h-3.5 w-3.5 text-emerald-400" />,
      onClick: () => navigate('/admin/health'),
    },
    {
      id: 'divider-2',
      label: '',
      divider: true,
    },
    {
      id: 'logout',
      label: 'Sign Out',
      icon: <LogOut className="h-3.5 w-3.5" />,
      variant: 'danger',
      onClick: handleLogout,
    },
  ];

  return (
    <header className="h-16 border-b border-border/80 bg-card/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Left: Mobile Menu Toggle & Search Bar / Cmd+K Trigger */}
      <div className="flex items-center gap-3 flex-1 max-w-lg">
        <button
          type="button"
          onClick={() => setMobileNavOpen(!isMobileNavOpen)}
          className="md:hidden p-2 rounded-lg border border-border text-muted-foreground hover:text-foreground"
          aria-label="Toggle navigation"
        >
          <Menu className="h-4 w-4" />
        </button>

        <button
          type="button"
          onClick={() => setOpen(true)}
          className="w-full flex items-center justify-between gap-3 px-3 py-1.5 rounded-lg border border-border/80 bg-background/60 hover:bg-background hover:border-primary/50 text-muted-foreground hover:text-foreground text-xs transition-colors shadow-sm"
        >
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <span>Search documents, commands, and investigations...</span>
          </div>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border/80 bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground font-semibold">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Health Status, Theme Toggle & User Profile */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* System Probe Indicator */}
        <button
          type="button"
          onClick={() => navigate('/admin/health')}
          className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-medium hover:bg-emerald-500/20 transition-colors"
          title="Cluster & API Status: Operational"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] font-mono font-semibold">API OK</span>
        </button>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="text-muted-foreground hover:text-foreground"
        >
          {effectiveTheme === 'dark' ? (
            <Sun className="h-4 w-4 text-amber-400" />
          ) : (
            <Moon className="h-4 w-4 text-indigo-500" />
          )}
        </Button>

        {/* User Profile Dropdown */}
        <DropdownMenu
          trigger={
            <div className="flex items-center gap-2 p-1 rounded-lg hover:bg-muted/60 transition-colors cursor-pointer">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-cyan-400 p-0.5 flex items-center justify-center shadow-sm">
                <div className="h-full w-full bg-slate-900 rounded-[6px] flex items-center justify-center text-xs font-bold text-cyan-300">
                  {user?.full_name ? user.full_name.charAt(0).toUpperCase() : <User className="h-3.5 w-3.5" />}
                </div>
              </div>
              <div className="hidden lg:flex flex-col text-left">
                <span className="text-xs font-semibold text-foreground truncate max-w-[120px]">
                  {user?.full_name || 'Investiga User'}
                </span>
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 font-mono">
                  {user?.is_superuser ? (
                    <span className="text-rose-400 flex items-center gap-0.5">
                      <Shield className="h-2.5 w-2.5" /> Root
                    </span>
                  ) : (
                    user?.roles?.[0] || 'Operator'
                  )}
                </span>
              </div>
            </div>
          }
          items={userMenuItems}
        />
      </div>
    </header>
  );
};
