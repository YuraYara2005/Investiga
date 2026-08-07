import { create } from 'zustand';

interface UIState {
  isSidebarCollapsed: boolean;
  isMobileNavOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setMobileNavOpen: (open: boolean) => void;
}

const SIDEBAR_STORAGE_KEY = 'investiga_sidebar_collapsed';

export const useUIStore = create<UIState>((set) => ({
  isSidebarCollapsed: localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true',
  isMobileNavOpen: false,

  toggleSidebar: () => {
    set((state) => {
      const next = !state.isSidebarCollapsed;
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
      return { isSidebarCollapsed: next };
    });
  },

  setSidebarCollapsed: (collapsed: boolean) => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    set({ isSidebarCollapsed: collapsed });
  },

  setMobileNavOpen: (open: boolean) => {
    set({ isMobileNavOpen: open });
  },
}));
