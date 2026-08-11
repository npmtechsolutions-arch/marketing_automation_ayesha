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
  PenSquare,
  Calendar,
  BarChart3,
  Lightbulb,
  Sparkles,
} from "lucide-react";
import { cn, getInitials } from "@/lib/utils";
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
  billing: "Billing",
  notifications: "Notifications",
};

const quickSearchLinks = [
  { label: "Create AI Post", icon: PenSquare, path: "/create-post", category: "Actions" },
  { label: "Content Calendar", icon: Calendar, path: "/calendar", category: "Navigation" },
  { label: "AI Marketing Strategy", icon: Lightbulb, path: "/strategy", category: "Intelligence" },
  { label: "Analytics Overview", icon: BarChart3, path: "/analytics", category: "Reports" },
  { label: "Account Settings", icon: Settings, path: "/settings", category: "Account" },
];

export default function TopBar() {
  const { setSidebarOpen, toggleNotifications, notificationsOpen, unreadCount, theme, toggleTheme } =
    useUIStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
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

  const initials = getInitials(user?.full_name);

  const filteredLinks = searchQuery.trim()
    ? quickSearchLinks.filter((l) =>
        l.label.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : quickSearchLinks;

  return (
    <header
      className="flex h-16 shrink-0 items-center justify-between gap-4 border-b px-4 backdrop-blur-2xl lg:px-8 z-30 select-none"
      style={{ backgroundColor: "var(--topbar-bg)", borderColor: "var(--surface-border)" }}
    >
      {/* Left side: Hamburger + Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(true)}
          className="rounded-xl p-2 transition-colors lg:hidden cursor-pointer hover:bg-[var(--sidebar-hover-bg)]"
          style={{ color: "var(--page-text-secondary)" }}
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Breadcrumbs */}
        <nav className="hidden items-center gap-1.5 text-sm font-medium lg:flex">
          {breadcrumbs.map((crumb) => (
            <div key={crumb.path} className="flex items-center gap-1.5">
              {crumb.path !== breadcrumbs[0]?.path && (
                <ChevronRight className="h-3.5 w-3.5" style={{ color: "var(--page-text-muted)" }} />
              )}
              <span
                className={cn(
                  "rounded-md px-1.5 py-0.5 transition-colors cursor-pointer",
                  crumb.isLast
                    ? "font-semibold"
                    : "hover:bg-[var(--sidebar-hover-bg)]"
                )}
                style={{
                  color: crumb.isLast ? "var(--page-heading)" : "var(--page-text-secondary)",
                }}
                onClick={() => !crumb.isLast && navigate(crumb.path)}
              >
                {crumb.label}
              </span>
            </div>
          ))}
        </nav>
      </div>

      {/* Center: Search Trigger Button */}
      <div className="flex flex-1 max-w-md justify-center px-2">
        <button
          onClick={() => setSearchOpen(true)}
          className="group flex w-full max-w-sm items-center gap-2.5 rounded-xl border px-3.5 py-2 text-xs font-medium backdrop-blur-md transition-all duration-200 cursor-pointer shadow-sm hover:border-[var(--accent-purple)] hover:shadow-md"
          style={{
            backgroundColor: "var(--input-bg)",
            borderColor: "var(--input-border)",
            color: "var(--input-placeholder)",
          }}
        >
          <Search className="h-3.5 w-3.5 transition-colors group-hover:text-[var(--accent-purple)]" />
          <span className="flex-1 text-left">Search pages, tools & AI features...</span>
          <kbd
            className="hidden rounded-lg border px-1.5 py-0.5 text-[10px] font-bold sm:inline-block tracking-widest shadow-xs"
            style={{
              backgroundColor: "var(--sidebar-hover-bg)",
              borderColor: "var(--surface-border)",
              color: "var(--page-text-muted)",
            }}
          >
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Actions (Create Post, Theme, Notifications, Avatar) */}
      <div className="flex items-center gap-2.5">
        {/* Quick Create Button */}
        <button
          onClick={() => navigate("/create-post")}
          className="hidden sm:inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-bold text-white shadow-md shadow-purple-500/20 transition-all duration-200 cursor-pointer hover:shadow-lg hover:shadow-purple-500/30 hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: "linear-gradient(135deg, #7c3aed, #6366f1)",
          }}
        >
          <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
          <span>New Post</span>
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="flex h-9 w-9 items-center justify-center rounded-xl border transition-all duration-200 cursor-pointer hover:border-[var(--accent-purple)] hover:bg-[var(--sidebar-hover-bg)]"
          style={{
            borderColor: "var(--surface-border)",
            color: "var(--page-text-secondary)",
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            {theme === "dark" ? (
              <motion.div
                key="sun"
                initial={{ rotate: -90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: 90, opacity: 0 }}
                transition={{ duration: 0.18 }}
              >
                <Sun className="h-4.5 w-4.5 text-amber-400" />
              </motion.div>
            ) : (
              <motion.div
                key="moon"
                initial={{ rotate: 90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: -90, opacity: 0 }}
                transition={{ duration: 0.18 }}
              >
                <Moon className="h-4.5 w-4.5 text-indigo-500" />
              </motion.div>
            )}
          </AnimatePresence>
        </button>

        {/* Notifications */}
        <div ref={notifRef} className="relative">
          <button
            onClick={toggleNotifications}
            aria-label="Notifications"
            className="relative flex h-9 w-9 items-center justify-center rounded-xl border transition-all duration-200 cursor-pointer hover:border-[var(--accent-purple)] hover:bg-[var(--sidebar-hover-bg)]"
            style={{
              borderColor: "var(--surface-border)",
              color: "var(--page-text-secondary)",
            }}
          >
            <Bell className="h-4.5 w-4.5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white ring-2 ring-[var(--topbar-bg)]">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>
          <AnimatePresence>
            {notificationsOpen && <NotificationPanel />}
          </AnimatePresence>
        </div>

        {/* User Menu Dropdown */}
        <div ref={userMenuRef} className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 via-indigo-500 to-blue-500 text-xs font-bold text-white shadow-md shadow-purple-500/20 ring-1 ring-white/20 transition-transform duration-200 cursor-pointer hover:scale-105"
          >
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt=""
                className="h-full w-full rounded-xl object-cover"
              />
            ) : (
              initials
            )}
          </button>

          <AnimatePresence>
            {userMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                style={{
                  backgroundColor: "var(--dropdown-bg)",
                  borderColor: "var(--dropdown-border)",
                  boxShadow: "var(--dropdown-shadow)",
                }}
                className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-2xl border p-1.5 backdrop-blur-xl"
              >
                <div className="px-3 py-2 border-b" style={{ borderColor: "var(--surface-border)" }}>
                  <p className="text-xs font-medium" style={{ color: "var(--page-text-muted)" }}>Signed in as</p>
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--page-heading)" }}>{user?.email}</p>
                </div>
                <div className="py-1">
                  {[
                    { label: "Your Profile", icon: User, path: "/profile" },
                    { label: "Account Settings", icon: Settings, path: "/settings" },
                    { label: "Billing & Plans", icon: CreditCard, path: "/billing" },
                  ].map((item) => (
                    <button
                      key={item.label}
                      onClick={() => {
                        setUserMenuOpen(false);
                        navigate(item.path);
                      }}
                      className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium rounded-xl transition-colors cursor-pointer"
                      style={{ color: "var(--page-text)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                    >
                      <item.icon className="h-4 w-4 text-purple-400" />
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="border-t pt-1" style={{ borderColor: "var(--surface-border)" }}>
                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium rounded-xl transition-colors cursor-pointer text-red-400 hover:bg-red-500/10 hover:text-red-300"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Global Quick Search Modal */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 pt-[12vh] px-4 backdrop-blur-md"
            onClick={() => {
              setSearchOpen(false);
              setSearchQuery("");
            }}
          >
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                backgroundColor: "var(--dropdown-bg)",
                borderColor: "var(--dropdown-border)",
                boxShadow: "var(--dropdown-shadow)",
              }}
              className="w-full max-w-xl overflow-hidden rounded-2xl border backdrop-blur-2xl"
            >
              <div
                className="flex items-center gap-3 border-b px-4 py-3.5"
                style={{ borderColor: "var(--surface-border)" }}
              >
                <Search className="h-5 w-5 text-purple-400" />
                <input
                  autoFocus
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search pages, tools, strategy, AI..."
                  className="flex-1 bg-transparent text-sm font-medium outline-none placeholder:text-gray-400"
                  style={{ color: "var(--page-heading)" }}
                />
                <kbd
                  className="rounded-lg border px-2 py-0.5 text-[10px] font-bold"
                  style={{
                    backgroundColor: "var(--sidebar-hover-bg)",
                    borderColor: "var(--surface-border)",
                    color: "var(--page-text-muted)",
                  }}
                >
                  ESC
                </kbd>
              </div>

              <div className="max-h-80 overflow-y-auto p-2">
                <p className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
                  Quick Navigation
                </p>
                <div className="space-y-1">
                  {filteredLinks.map((link) => (
                    <button
                      key={link.path}
                      onClick={() => {
                        setSearchOpen(false);
                        setSearchQuery("");
                        navigate(link.path);
                      }}
                      className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium transition-colors cursor-pointer"
                      style={{ color: "var(--page-text)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="flex h-8 w-8 items-center justify-center rounded-lg"
                          style={{
                            backgroundColor: "rgba(109,94,246,0.12)",
                            color: "var(--accent-purple)",
                          }}
                        >
                          <link.icon className="h-4 w-4" />
                        </div>
                        <span>{link.label}</span>
                      </div>
                      <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                        {link.category}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
