import { create } from "zustand";

type Theme = "dark" | "light";

interface UIState {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  currentAccountId: string | null;
  theme: Theme;
  notificationsOpen: boolean;
  unreadCount: number;
}

interface UIActions {
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  collapseSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setCurrentAccount: (accountId: string | null) => void;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  toggleNotifications: () => void;
  setUnreadCount: (count: number) => void;
}

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return "light";
}

function getInitialSidebar(): boolean {
  const stored = localStorage.getItem("sidebar_collapsed");
  return stored === "true";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.remove("dark", "light");
  root.classList.add(theme);
  localStorage.setItem("theme", theme);
}

// Apply the stored theme immediately on load
applyTheme(getInitialTheme());

export const useUIStore = create<UIState & UIActions>((set) => ({
  sidebarOpen: true,
  sidebarCollapsed: getInitialSidebar(),
  currentAccountId: localStorage.getItem("current_account_id"),
  theme: getInitialTheme(),
  notificationsOpen: false,
  unreadCount: 0,

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open: boolean) =>
    set({ sidebarOpen: open }),

  collapseSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      localStorage.setItem("sidebar_collapsed", String(next));
      return { sidebarCollapsed: next };
    }),

  setSidebarCollapsed: (collapsed: boolean) => {
    localStorage.setItem("sidebar_collapsed", String(collapsed));
    set({ sidebarCollapsed: collapsed });
  },

  setCurrentAccount: (accountId: string | null) => {
    if (accountId) {
      localStorage.setItem("current_account_id", accountId);
    } else {
      localStorage.removeItem("current_account_id");
    }
    set({ currentAccountId: accountId });
  },

  setTheme: (theme: Theme) => {
    applyTheme(theme);
    set({ theme });
  },

  toggleTheme: () =>
    set((state) => {
      const next = state.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      return { theme: next };
    }),

  toggleNotifications: () =>
    set((state) => ({ notificationsOpen: !state.notificationsOpen })),

  setUnreadCount: (count: number) =>
    set({ unreadCount: count }),
}));
