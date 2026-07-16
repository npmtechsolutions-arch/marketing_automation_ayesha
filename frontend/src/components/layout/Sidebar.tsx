import { useRef, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";
import { useAuthStore } from "@/stores/authStore";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { label: "Create Post", icon: PenSquare, path: "/create-post" },
  { label: "Content Calendar", icon: Calendar, path: "/calendar" },
  { label: "Platforms", icon: Share2, path: "/platforms" },
  { label: "Accounts", icon: UserCircle, path: "/social-accounts" },
  { label: "Analytics", icon: BarChart3, path: "/analytics" },
  { label: "Strategy", icon: Lightbulb, path: "/strategy" },
  { label: "Campaigns", icon: Megaphone, path: "/campaigns" },
  { label: "Activity Log", icon: Activity, path: "/activity" },
  { label: "Team", icon: Users, path: "/team" },
];

// Secondary nav — account-level pages shown below a divider
const secondaryNavItems = [
  { label: "Notifications", icon: Bell, path: "/notifications" },
  { label: "Billing", icon: CreditCard, path: "/billing" },
  { label: "Settings", icon: Settings, path: "/settings" },
  { label: "Help Center", icon: HelpCircle, path: "/help" },
];

// Admin-only nav
const adminNavItems = [
  { label: "Admin", icon: ShieldCheck, path: "/admin" },
];

const sidebarVariants = {
  expanded: { width: 260 },
  collapsed: { width: 72 },
};

const itemVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.3, ease: "easeOut" as const },
  }),
};

function UserSection({ collapsed }: { collapsed: boolean }) {
  const { user, logout } = useAuthStore();
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

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "ME";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg p-2 transition-colors hover:bg-white/5",
          collapsed && "justify-center"
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-blue-500 text-xs font-bold text-white">
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt=""
              className="h-full w-full rounded-full object-cover"
            />
          ) : (
            initials
          )}
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1 text-left">
            <p className="truncate text-sm font-medium text-white">
              {user?.full_name ?? "User"}
            </p>
            <p className="truncate text-xs text-slate-400">
              {user?.role ?? "Member"}
            </p>
          </div>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "absolute bottom-full left-0 z-50 mb-2 w-48 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-xl",
              collapsed && "left-full ml-2 bottom-0"
            )}
          >
            <NavLink
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2.5 text-sm text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
            >
              <User className="h-4 w-4" />
              Profile
            </NavLink>
            <button
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-red-400 transition-colors hover:bg-red-500/10 hover:text-red-300"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

import { useState } from "react";

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
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-white/5 bg-slate-950/95 backdrop-blur-xl lg:hidden"
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
        transition={{ type: "spring", damping: 25, stiffness: 300 }}
        className="hidden flex-col border-r border-white/5 bg-slate-950/80 backdrop-blur-xl lg:flex"
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
    item: { label: string; icon: typeof LayoutDashboard; path: string },
    i: number
  ) => {
    const isActive =
      currentPath === item.path ||
      (item.path !== "/dashboard" && currentPath.startsWith(item.path));

    return (
      <motion.li
        key={item.path}
        custom={i}
        variants={itemVariants}
        initial="hidden"
        animate="visible"
      >
        <NavLink
          to={item.path}
          onClick={onClose}
          className={cn(
            "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
            collapsed && "justify-center px-0",
            isActive
              ? "border-l-2 border-purple-500 bg-purple-500/20 text-white"
              : "border-l-2 border-transparent text-slate-400 hover:bg-white/5 hover:text-white"
          )}
        >
          <item.icon
            className={cn(
              "h-5 w-5 shrink-0 transition-colors",
              isActive ? "text-purple-400" : "text-slate-400 group-hover:text-white"
            )}
          />
          {!collapsed && <span>{item.label}</span>}

          {/* Tooltip for collapsed */}
          {collapsed && (
            <div className="pointer-events-none absolute left-full ml-3 hidden rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-sm text-white shadow-xl group-hover:block">
              {item.label}
            </div>
          )}
        </NavLink>
      </motion.li>
    );
  };

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div
        className={cn(
          "flex h-16 shrink-0 items-center border-b border-white/5 px-4",
          collapsed ? "justify-center" : "justify-between"
        )}
      >
        <div className="flex items-center gap-2.5">
          <img
            src="/marketengine_logo.png"
            alt="MarketEngine AI"
            className="h-8 w-8 shrink-0 rounded-lg object-cover shadow-lg shadow-purple-500/20"
          />
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-lg font-bold text-transparent"
            >
              MarketEngine
            </motion.span>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/5 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        )}
        {onToggleCollapse && !onClose && (
          <button
            onClick={onToggleCollapse}
            className={cn(
              "rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/5 hover:text-white",
              collapsed && "mx-auto"
            )}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {navItems.map((item, i) => renderItem(item, i))}
        </ul>

        {/* Divider */}
        <div className="my-3 border-t border-white/5" />

        <ul className="space-y-1">
          {secondaryNavItems.map((item, i) => renderItem(item, navItems.length + i))}
        </ul>

        {isAdmin && (
          <>
            <div className="my-3 border-t border-white/5" />
            {!collapsed && (
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Administration
              </p>
            )}
            <ul className="space-y-1">
              {adminNavItems.map((item, i) =>
                renderItem(item, navItems.length + secondaryNavItems.length + i)
              )}
            </ul>
          </>
        )}
      </nav>

      {/* User section */}
      <div className="shrink-0 border-t border-white/5 p-3">
        <UserSection collapsed={collapsed} />
      </div>
    </div>
  );
}
