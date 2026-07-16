import { useState, useRef, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Menu,
  Search,
  Plus,
  Bell,
  ChevronRight,
  User,
  Settings,
  CreditCard,
  LogOut,
  Sun,
  Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { useAuthStore } from "@/stores/authStore";
import NotificationPanel from "@/components/shared/NotificationPanel";

const breadcrumbMap: Record<string, string> = {
  dashboard: "Dashboard",
  calendar: "Content Calendar",
  create: "Create Post",
  "create-post": "Create Post",
  analytics: "Analytics",
  strategy: "Strategy",
  campaigns: "Campaigns",
  platforms: "Platforms",
  "social-accounts": "Social Accounts",
  activity: "Activity Log",
  team: "Team",
  settings: "Settings",
  profile: "Profile",
};

export default function TopBar() {
  const { setSidebarOpen, toggleNotifications, notificationsOpen, unreadCount, theme, toggleTheme } =
    useUIStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [searchOpen, setSearchOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  // Close menus on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(e.target as Node)
      ) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Cmd+K shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Build breadcrumbs
  const segments = location.pathname.split("/").filter(Boolean);
  const breadcrumbs = segments.map((seg, i) => ({
    label: breadcrumbMap[seg] ?? seg.charAt(0).toUpperCase() + seg.slice(1),
    path: "/" + segments.slice(0, i + 1).join("/"),
    isLast: i === segments.length - 1,
  }));

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "ME";

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-white/5 bg-slate-900/50 px-4 backdrop-blur-xl lg:px-6">
      {/* Mobile hamburger */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Breadcrumbs */}
      <nav className="hidden items-center gap-1 text-sm lg:flex">
        {breadcrumbs.map((crumb) => (
          <div key={crumb.path} className="flex items-center gap-1">
            {crumb.path !== breadcrumbs[0]?.path && (
              <ChevronRight className="h-3.5 w-3.5 text-slate-600" />
            )}
            <span
              className={cn(
                crumb.isLast
                  ? "font-medium text-white"
                  : "cursor-pointer text-slate-400 transition-colors hover:text-white"
              )}
              onClick={() => !crumb.isLast && navigate(crumb.path)}
            >
              {crumb.label}
            </span>
          </div>
        ))}
      </nav>

      {/* Search bar - center */}
      <div className="mx-auto flex max-w-md flex-1 justify-center px-4">
        <button
          onClick={() => setSearchOpen(true)}
          className="flex w-full max-w-sm items-center gap-3 rounded-xl border border-white/5 bg-white/5 px-4 py-2 text-sm text-slate-400 backdrop-blur-sm transition-all hover:border-white/10 hover:bg-white/[0.07]"
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">Search...</span>
          <kbd className="hidden rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 sm:block">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-2">
        {/* Quick create */}
        <button
          onClick={() => navigate("/create-post")}
          style={{ backgroundColor: "#7c3aed", color: "#ffffff" }}
          className="flex h-8 w-8 items-center justify-center rounded-lg shadow-sm transition-transform hover:scale-105 active:scale-95"
        >
          <Plus className="h-4 w-4" />
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>

        {/* Notifications */}
        <div ref={notifRef} className="relative">
          <button
            onClick={toggleNotifications}
            className="relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
              </span>
            )}
          </button>
          <AnimatePresence>
            {notificationsOpen && <NotificationPanel />}
          </AnimatePresence>
        </div>

        {/* User avatar dropdown */}
        <div ref={userMenuRef} className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-blue-500 text-xs font-bold text-white transition-transform hover:scale-105"
          >
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt=""
                className="h-full w-full rounded-full object-cover"
              />
            ) : (
              initials
            )}
          </button>
          <AnimatePresence>
            {userMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl"
              >
                <div className="border-b border-white/5 px-4 py-3">
                  <p className="text-sm font-medium text-white">
                    {user?.full_name ?? "User"}
                  </p>
                  <p className="text-xs text-slate-400">{user?.email ?? ""}</p>
                </div>
                <div className="py-1">
                  {[
                    { label: "Profile", icon: User, path: "/profile" },
                    { label: "Settings", icon: Settings, path: "/settings" },
                    { label: "Billing", icon: CreditCard, path: "/billing" },
                  ].map((item) => (
                    <button
                      key={item.label}
                      onClick={() => {
                        setUserMenuOpen(false);
                        navigate(item.path);
                      }}
                      className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
                    >
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="border-t border-white/5 py-1">
                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-400 transition-colors hover:bg-red-500/10 hover:text-red-300"
                  >
                    <LogOut className="h-4 w-4" />
                    Logout
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Search modal overlay */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 pt-[15vh] backdrop-blur-sm"
            onClick={() => setSearchOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl"
            >
              <div className="flex items-center gap-3 border-b border-white/5 px-4 py-3">
                <Search className="h-5 w-5 text-slate-400" />
                <input
                  autoFocus
                  type="text"
                  placeholder="Search posts, campaigns, analytics..."
                  className="flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
                />
                <kbd className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500">
                  ESC
                </kbd>
              </div>
              <div className="px-4 py-8 text-center text-sm text-slate-500">
                Start typing to search...
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
