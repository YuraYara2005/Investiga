import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  BookOpen,
  FileSearch,
  Bot,
  BarChart2,
  Activity,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Shield,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores/useUIStore';
import { useAuth } from '@/auth/useAuth';
import type { NavigationSection } from '@/types/common';

export const Sidebar: React.FC = () => {
  const { isSidebarCollapsed, toggleSidebar, setMobileNavOpen } = useUIStore();
  const { hasPermission, isSuperuser } = useAuth();

  const navigationSections: NavigationSection[] = [
    {
      title: 'OPERATIONS',
      items: [
        {
          name: 'Dashboard',
          href: '/dashboard',
          icon: LayoutDashboard,
        },
        {
          name: 'Knowledge Base',
          href: '/knowledge',
          icon: BookOpen,
        },
      ],
    },
    {
      title: 'INCIDENT INVESTIGATION',
      items: [
        {
          name: 'Search Workbench',
          href: '/search',
          icon: FileSearch,
          badge: 'Shell',
        },
        {
          name: 'AI Assistant (RAG)',
          href: '/chat',
          icon: Bot,
          badge: 'Shell',
        },
        {
          name: 'Evaluation & Benchmarks',
          href: '/evaluation',
          icon: BarChart2,
          badge: 'Shell',
        },
      ],
    },
    {
      title: 'SYSTEM & ADMIN',
      items: [
        {
          name: 'Health Probes',
          href: '/admin/health',
          icon: Activity,
        },
        {
          name: 'RBAC Matrix',
          href: '/admin/roles',
          icon: ShieldCheck,
        },
      ],
    },
  ];

  return (
    <aside
      className={cn(
        'relative flex flex-col border-r border-border/80 bg-card/95 transition-all duration-200 ease-in-out z-30 select-none backdrop-blur-md',
        isSidebarCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-border/60">
        <NavLink
          to="/dashboard"
          className="flex items-center gap-3 overflow-hidden"
          onClick={() => setMobileNavOpen(false)}
        >
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-indigo-600 to-cyan-500 p-0.5 shadow-md shadow-indigo-500/20 flex-shrink-0 flex items-center justify-center">
            <div className="h-full w-full bg-slate-950 rounded-[7px] flex items-center justify-center">
              <Shield className="h-4 w-4 text-cyan-400" />
            </div>
          </div>
          {!isSidebarCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-sm tracking-tight text-foreground flex items-center gap-1.5">
                INVESTIGA
                <span className="text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                  v1.0
                </span>
              </span>
              <span className="text-[10px] text-muted-foreground truncate">
                Incident Intelligence
              </span>
            </div>
          )}
        </NavLink>

        <button
          type="button"
          onClick={toggleSidebar}
          className="hidden md:flex h-6 w-6 rounded border border-border/80 items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isSidebarCollapsed ? (
            <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <ChevronLeft className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto py-4 px-2 space-y-6">
        {navigationSections.map((section, idx) => {
          const visibleItems = section.items.filter((item) => {
            if (item.requiredPermission && !hasPermission(item.requiredPermission) && !isSuperuser) {
              return false;
            }
            return true;
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={idx} className="space-y-1">
              {!isSidebarCollapsed && (
                <p className="px-3 text-[10px] font-bold text-muted-foreground/80 uppercase tracking-wider mb-2">
                  {section.title}
                </p>
              )}
              {visibleItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.href}
                    to={item.href}
                    onClick={() => setMobileNavOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'group flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors relative',
                        isActive
                          ? 'bg-primary/10 text-primary font-semibold'
                          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                        isSidebarCollapsed && 'justify-center px-0'
                      )
                    }
                    title={isSidebarCollapsed ? item.name : undefined}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          className={cn(
                            'h-4 w-4 flex-shrink-0 transition-transform group-hover:scale-105',
                            isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                          )}
                        />
                        {!isSidebarCollapsed && (
                          <span className="truncate flex-1">{item.name}</span>
                        )}
                        {!isSidebarCollapsed && item.badge && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border/40">
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Bottom Status Indicator */}
      <div className="p-3 border-t border-border/60">
        <div
          className={cn(
            'flex items-center gap-2 p-2 rounded-md bg-muted/40 text-xs',
            isSidebarCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
            {!isSidebarCollapsed && (
              <span className="text-[11px] font-medium text-foreground truncate">
                Engine Active
              </span>
            )}
          </div>
          {!isSidebarCollapsed && (
            <span className="font-mono text-[10px] text-muted-foreground">
              v1.0.0
            </span>
          )}
        </div>
      </div>
    </aside>
  );
};
