import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import { ToastContainer } from '@/components/ui/Toast';
import { ErrorBoundary } from '@/components/feedback/ErrorBoundary';
import { useUIStore } from '@/stores/useUIStore';
import { cn } from '@/lib/utils';

export const AppLayout: React.FC = () => {
  const { isMobileNavOpen, setMobileNavOpen } = useUIStore();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Mobile Drawer Overlay */}
      {isMobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* Sidebar (Responsive on Desktop & Mobile) */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 md:static transition-transform duration-200 ease-in-out md:translate-x-0 flex',
          isMobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <Sidebar />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <TopNav />

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>

      {/* Global Interactive Utilities */}
      <CommandPalette />
      <ToastContainer />
    </div>
  );
};
