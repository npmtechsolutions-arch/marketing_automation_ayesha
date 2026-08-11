import { useState, useRef, useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Calendar,
  PenSquare,
  BarChart3,
  Lightbulb,
  Megaphone,
  Share2,
  Users,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  User,
  X,
  UserCircle,
  Activity,
  Bell,
  CreditCard,
  HelpCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { cn, getInitials } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { useAuthStore } from "@/stores/authStore";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, path: "/dashboard", badge: null },
  { label: "Create Post", icon: PenSquare, path: "/create-post", badge: "AI" },
  { label: "Content Calendar", icon: Calendar, path: "/calendar", badge: null },
  { label: "Platforms", icon: Share2, path: "/platforms", badge: null },
  { label: "Accounts", icon: UserCircle, path: "/social-accounts", badge: null },
  { label: "Analytics", icon: BarChart3, path: "/analytics", badge: null },
  { label: "Strategy", icon: Lightbulb, path: "/strategy", badge: "New" },
  { label: "Campaigns", icon: Megaphone, path: "/campaigns", badge: null },
  { label: "Activity Log", icon: Activity, path: "/activity", badge: null },
  { label: "Team", icon: Users, path: "/team", badge: null },
];

const secondaryNavItems = [
  { label: "Notifications", icon: Bell, path: "/notifications" },
  { label: "Billing", icon: CreditCard, path: "/billing" },
  { label: "Settings", icon: Settings, path: "/settings" },
  { label: "Help Center", icon: HelpCircle, path: "/help" },
];

const adminNavItems = [
  { label: "Admin Panel", icon: ShieldCheck, path: "/admin" },
];

const sidebarVariants = {
  expanded: { width: 264 },
  collapsed: { width: 76 },
};

function UserSection({ collapsed }: { collapsed: boolean }) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const initials = getInitials(user?.full_name);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "group flex w-full items-center gap-3 rounded-xl p-2.5 transition-all duration-200 cursor-pointer",
          collapsed ? "justify-center" : "hover:bg-[var(--sidebar-hover-bg)]"
        )}
      >
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 via-indigo-500 to-blue-500 text-xs font-bold text-white shadow-md shadow-purple-500/20 ring-1 ring-white/20">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt=""
              className="h-full w-full rounded-xl object-cover"
            />
          ) : (
            initials
          )}
          <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-[var(--sidebar-bg)]" />
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1 text-left">
            <p className="truncate text-sm font-semibold" style={{ color: "var(--page-heading)" }}>
              {user?.full_name ?? "User"}
            </p>
            <p className="truncate text-xs capitalize" style={{ color: "var(--page-text-muted)" }}>
              {user?.role ?? "Member"}
            </p>
          </div>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.96 }}
            transition={{ duration: 0.16 }}
            style={{
              backgroundColor: "var(--dropdown-bg)",
              borderColor: "var(--dropdown-border)",
              boxShadow: "var(--dropdown-shadow)",
            }}
            className={cn(
              "absolute bottom-full left-0 z-50 mb-2 w-56 overflow-hidden rounded-2xl border p-1.5 backdrop-blur-xl",
              collapsed && "left-full ml-3 bottom-0"
            )}
          >
            <div className="px-3 py-2 border-b" style={{ borderColor: "var(--surface-border)" }}>
              <p className="text-xs font-medium" style={{ color: "var(--page-text-muted)" }}>Signed in as</p>
              <p className="text-sm font-semibold truncate" style={{ color: "var(--page-heading)" }}>{user?.email}</p>
            </div>
            <div className="py-1">
              <button
                onClick={() => {
                  setOpen(false);
                  navigate("/profile");
                }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium rounded-xl transition-colors cursor-pointer"
                style={{ color: "var(--page-text)" }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
              >
                <User className="h-4 w-4 text-purple-400" />
                Your Profile
              </button>
              <button
                onClick={() => {
                  setOpen(false);
                  navigate("/settings");
                }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm font-medium rounded-xl transition-colors cursor-pointer"
                style={{ color: "var(--page-text)" }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--sidebar-hover-bg)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
              >
                <Settings className="h-4 w-4 text-blue-400" />
                Settings
              </button>
            </div>
            <div className="border-t pt-1" style={{ borderColor: "var(--surface-border)" }}>
              <button
                onClick={() => {
                  setOpen(false);
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
  );
}

export default function Sidebar() {
  const { sidebarCollapsed, collapseSidebar, sidebarOpen, setSidebarOpen } =
    useUIStore();
  const location = useLocation();

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 26, stiffness: 320 }}
              className="fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r backdrop-blur-2xl lg:hidden"
              style={{ backgroundColor: "var(--sidebar-bg)", borderColor: "var(--sidebar-border)" }}
            >
              <SidebarContent
                collapsed={false}
                onClose={() => setSidebarOpen(false)}
                currentPath={location.pathname}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <motion.aside
        variants={sidebarVariants}
        animate={sidebarCollapsed ? "collapsed" : "expanded"}
        transition={{ type: "spring", damping: 26, stiffness: 320 }}
        className="hidden flex-col border-r backdrop-blur-2xl lg:flex select-none"
        style={{ backgroundColor: "var(--sidebar-bg)", borderColor: "var(--sidebar-border)" }}
      >
        <SidebarContent
          collapsed={sidebarCollapsed}
          onToggleCollapse={collapseSidebar}
          currentPath={location.pathname}
        />
      </motion.aside>
    </>
  );
}

function SidebarContent({
  collapsed,
  onClose,
  onToggleCollapse,
  currentPath,
}: {
  collapsed: boolean;
  onClose?: () => void;
  onToggleCollapse?: () => void;
  currentPath: string;
}) {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "admin" || role === "super_admin" || role === "superadmin";

  const renderItem = (
    item: { label: string; icon: typeof LayoutDashboard; path: string; badge?: string | null }
  ) => {
    const isActive =
      currentPath === item.path ||
      (item.path !== "/dashboard" && currentPath.startsWith(item.path));

    return (
      <li key={item.path} className="relative">
        <NavLink
          to={item.path}
          onClick={onClose}
          className={cn(
            "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200 cursor-pointer",
            collapsed && "justify-center px-0 h-10 w-10 mx-auto",
            isActive
              ? "text-white font-semibold"
              : "text-[var(--sidebar-text)] hover:text-[var(--page-heading)] hover:bg-[var(--sidebar-hover-bg)]"
          )}
        >
          {/* Active indicator pill */}
          {isActive && (
            <motion.div
              layoutId="sidebarActivePill"
              className="absolute inset-0 rounded-xl bg-gradient-to-r from-purple-600/90 to-indigo-600/90 shadow-md shadow-purple-500/25"
              transition={{ type: "spring", stiffness: 400, damping: 32 }}
            />
          )}

          <item.icon
            className={cn(
              "relative z-10 h-4.5 w-4.5 shrink-0 transition-transform duration-200 group-hover:scale-110",
              isActive ? "text-white" : "text-[var(--sidebar-text)] group-hover:text-[var(--page-heading)]"
            )}
          />

          {!collapsed && (
            <span className="relative z-10 flex-1 truncate">{item.label}</span>
          )}

          {!collapsed && item.badge && !isActive && (
            <span className="relative z-10 rounded-md bg-purple-500/15 px-1.5 py-0.5 text-[10px] font-bold text-purple-400 border border-purple-500/20">
              {item.badge}
            </span>
          )}

          {/* Tooltip for collapsed */}
          {collapsed && (
            <div className="pointer-events-none absolute left-full ml-3 hidden rounded-xl border px-3 py-1.5 text-xs font-semibold shadow-xl backdrop-blur-xl group-hover:block z-50 whitespace-nowrap"
              style={{
                backgroundColor: "var(--dropdown-bg)",
                borderColor: "var(--dropdown-border)",
                color: "var(--page-heading)",
                boxShadow: "var(--dropdown-shadow)",
              }}
            >
              {item.label}
              {item.badge && (
                <span className="ml-1.5 text-[10px] text-purple-400 font-bold">({item.badge})</span>
              )}
            </div>
          )}
        </NavLink>
      </li>
    );
  };

  return (
    <div className="flex h-full flex-col">
      {/* Logo Header */}
      <div
        className={cn(
          "flex h-16 shrink-0 items-center px-4 border-b",
          collapsed ? "justify-center" : "justify-between"
        )}
        style={{ borderColor: "var(--sidebar-border)" }}
      >
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 shadow-md shadow-purple-500/20 p-1.5 ring-1 ring-white/20">
            <img
              src="/marketengine_logo.png"
              alt="MarketEngine"
              className="h-full w-full rounded-lg object-cover"
            />
          </div>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="flex flex-col"
            >
              <span className="bg-gradient-to-r from-purple-400 via-indigo-400 to-blue-400 bg-clip-text text-base font-extrabold tracking-tight text-transparent">
                MarketEngine
              </span>
              <span className="text-[10px] font-medium tracking-wide uppercase" style={{ color: "var(--page-text-muted)" }}>
                Marketing AI
              </span>
            </motion.div>
          )}
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/5 hover:text-white lg:hidden cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        )}

        {onToggleCollapse && !onClose && (
          <button
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "rounded-lg p-1.5 transition-colors cursor-pointer hover:bg-[var(--sidebar-hover-bg)]",
              collapsed && "hidden"
            )}
            style={{ color: "var(--page-text-secondary)" }}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        <div>
          {!collapsed && (
            <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
              Core
            </p>
          )}
          <ul className="space-y-1">
            {navItems.map((item) => renderItem(item))}
          </ul>
        </div>

        <div>
          {!collapsed && (
            <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
              Account & Support
            </p>
          )}
          <ul className="space-y-1">
            {secondaryNavItems.map((item) => renderItem(item))}
          </ul>
        </div>

        {isAdmin && (
          <div>
            {!collapsed && (
              <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
                Administration
              </p>
            )}
            <ul className="space-y-1">
              {adminNavItems.map((item) => renderItem(item))}
            </ul>
          </div>
        )}
      </nav>

      {/* Collapse button when collapsed */}
      {collapsed && onToggleCollapse && (
        <div className="px-3 py-2 flex justify-center border-t" style={{ borderColor: "var(--sidebar-border)" }}>
          <button
            onClick={onToggleCollapse}
            aria-label="Expand sidebar"
            className="flex h-8 w-8 items-center justify-center rounded-xl transition-colors cursor-pointer hover:bg-[var(--sidebar-hover-bg)]"
            style={{ color: "var(--page-text-secondary)" }}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* User Section Footer */}
      <div className="shrink-0 border-t p-3" style={{ borderColor: "var(--sidebar-border)" }}>
        <UserSection collapsed={collapsed} />
      </div>
    </div>
  );
}
