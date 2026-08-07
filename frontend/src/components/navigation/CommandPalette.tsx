import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  LayoutDashboard,
  BookOpen,
  UploadCloud,
  FileSearch,
  Bot,
  BarChart2,
  Settings,
  Activity,
  ShieldAlert,
  Sun,
  Moon,
} from 'lucide-react';
import { useCommandStore } from '@/stores/useCommandStore';
import { useThemeStore } from '@/stores/useThemeStore';

interface CommandItem {
  id: string;
  title: string;
  category: string;
  icon: React.ReactNode;
  action: () => void;
  shortcut?: string;
}

export const CommandPalette: React.FC = () => {
  const { isOpen, setOpen } = useCommandStore();
  const { toggleTheme, effectiveTheme } = useThemeStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  // Keyboard shortcut listener (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(!isOpen);
      }
      if (e.key === 'Escape' && isOpen) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, setOpen]);

  const items: CommandItem[] = [
    {
      id: 'nav-dashboard',
      title: 'Go to Executive Dashboard',
      category: 'Navigation',
      icon: <LayoutDashboard className="h-4 w-4 text-indigo-400" />,
      action: () => {
        navigate('/dashboard');
        setOpen(false);
      },
    },
    {
      id: 'nav-knowledge',
      title: 'Knowledge Base Documents',
      category: 'Navigation',
      icon: <BookOpen className="h-4 w-4 text-cyan-400" />,
      action: () => {
        navigate('/knowledge');
        setOpen(false);
      },
    },
    {
      id: 'nav-upload',
      title: 'Upload Incident Runbook / Document',
      category: 'Actions',
      icon: <UploadCloud className="h-4 w-4 text-emerald-400" />,
      action: () => {
        navigate('/knowledge?action=upload');
        setOpen(false);
      },
      shortcut: 'U',
    },
    {
      id: 'nav-search',
      title: 'Hybrid Incident Search',
      category: 'Investigation',
      icon: <FileSearch className="h-4 w-4 text-cyan-400" />,
      action: () => {
        navigate('/search');
        setOpen(false);
      },
    },
    {
      id: 'nav-chat',
      title: 'AI Investigation Assistant (RAG)',
      category: 'Investigation',
      icon: <Bot className="h-4 w-4 text-indigo-400" />,
      action: () => {
        navigate('/chat');
        setOpen(false);
      },
    },
    {
      id: 'nav-evaluation',
      title: 'Evaluation & Benchmarks',
      category: 'Intelligence',
      icon: <BarChart2 className="h-4 w-4 text-amber-400" />,
      action: () => {
        navigate('/evaluation');
        setOpen(false);
      },
    },
    {
      id: 'nav-health',
      title: 'Platform System Health Probes',
      category: 'Administration',
      icon: <Activity className="h-4 w-4 text-emerald-400" />,
      action: () => {
        navigate('/admin/health');
        setOpen(false);
      },
    },
    {
      id: 'nav-roles',
      title: 'RBAC Roles & Entitlements Matrix',
      category: 'Administration',
      icon: <ShieldAlert className="h-4 w-4 text-rose-400" />,
      action: () => {
        navigate('/admin/roles');
        setOpen(false);
      },
    },
    {
      id: 'nav-settings',
      title: 'Profile & Security Settings',
      category: 'Account',
      icon: <Settings className="h-4 w-4 text-muted-foreground" />,
      action: () => {
        navigate('/settings');
        setOpen(false);
      },
    },
    {
      id: 'action-theme',
      title: effectiveTheme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode',
      category: 'Preferences',
      icon: effectiveTheme === 'dark' ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-indigo-400" />,
      action: () => {
        toggleTheme();
        setOpen(false);
      },
      shortcut: 'T',
    },
  ];

  const filteredItems = items.filter((item) =>
    item.title.toLowerCase().includes(query.toLowerCase()) ||
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-20 sm:pt-28">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ duration: 0.15 }}
            className="relative w-full max-w-xl z-10 overflow-hidden rounded-xl border border-border/80 bg-card shadow-2xl shadow-black/50"
          >
            <div className="flex items-center px-4 border-b border-border/60">
              <Search className="h-4 w-4 text-muted-foreground mr-3 flex-shrink-0" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a command or search destination..."
                className="h-12 w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                autoFocus
              />
              <kbd className="hidden sm:inline-flex items-center rounded border border-border/60 bg-muted/50 px-1.5 font-mono text-[10px] text-muted-foreground">
                ESC
              </kbd>
            </div>

            <div className="max-h-80 overflow-y-auto p-2">
              {filteredItems.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-foreground">
                  No commands matching &ldquo;{query}&rdquo;
                </div>
              ) : (
                <div className="space-y-1">
                  {filteredItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={item.action}
                      className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg text-foreground hover:bg-accent hover:text-accent-foreground transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <span className="p-1 rounded-md bg-muted/40 group-hover:bg-accent">
                          {item.icon}
                        </span>
                        <span>{item.title}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">
                          {item.category}
                        </span>
                        {item.shortcut && (
                          <kbd className="rounded border border-border/60 bg-muted/50 px-1.5 font-mono text-[10px] text-muted-foreground">
                            {item.shortcut}
                          </kbd>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-4 py-2 border-t border-border/60 bg-muted/30 text-[11px] text-muted-foreground">
              <span>Navigate with arrow keys</span>
              <div className="flex items-center gap-2">
                <span>Select: <kbd className="font-mono">↵</kbd></span>
                <span>Close: <kbd className="font-mono">Esc</kbd></span>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
