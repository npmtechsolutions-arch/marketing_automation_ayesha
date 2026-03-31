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
  sidebarCollapsed: false,
  currentAccountId: localStorage.getItem("current_account_id"),
  theme: getInitialTheme(),
  notificationsOpen: false,
  unreadCount: 0,

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open: boolean) =>
    set({ sidebarOpen: open }),

  collapseSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

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
