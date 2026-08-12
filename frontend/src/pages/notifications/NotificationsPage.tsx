import { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BellOff,
  CheckCheck,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────
type NotifType = "posts" | "strategy" | "team" | "billing" | "system";

interface Notification {
  id: string;
  type: NotifType;
  title: string;
  message: string;
  time: string;
  read: boolean;
  actionUrl?: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
}

const filterTabs: { id: string; label: string; type?: NotifType }[] = [
  { id: "all", label: "All" },
  { id: "unread", label: "Unread" },
  { id: "posts", label: "Posts", type: "posts" },
  { id: "strategy", label: "Strategy", type: "strategy" },
  { id: "team", label: "Team", type: "team" },
  { id: "billing", label: "Billing", type: "billing" },
  { id: "system", label: "System", type: "system" },
];

const ITEMS_PER_PAGE = 8;

// ── Component ───────────────────────────────────────────────────────

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch notifications from API
  useEffect(() => {
    api.get("/notifications/?limit=50")
      .then((res: any) => {
        const payload = res.data || res;
        const items: any[] = payload.items || payload || [];
        // Map backend notification shape to local type
        const mapped: Notification[] = items.map((n: any) => ({
          id: n.id,
          type: (n.notification_type || n.type || "system") as NotifType,
          title: n.title || n.subject || "Notification",
          message: n.message || n.body || "",
          time: n.created_at
            ? new Date(n.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
            : "",
          read: n.is_read ?? n.read ?? false,
          icon: BellOff, // fallback icon; replace per type if available
          iconColor: "text-purple-400",
          iconBg: "bg-purple-500/10",
        }));
        setNotifications(mapped);
      })
      .catch(() => setNotifications([]))
      .finally(() => setLoading(false));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const filtered = useMemo(() => {
    if (activeFilter === "all") return notifications;
    if (activeFilter === "unread") return notifications.filter((n) => !n.read);
    return notifications.filter((n) => n.type === activeFilter);
  }, [notifications, activeFilter]);

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE);
  const paginated = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const markAllRead = async () => {
    try {
      await api.post("/notifications/mark-all-read");
    } catch {}
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const markAsRead = async (id: string) => {
    try {
      await api.post(`/notifications/${id}/mark-read`);
    } catch {}
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n));
  };

  const deleteNotification = async (id: string) => {
    try {
      await api.delete(`/notifications/${id}`);
    } catch {}
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const getEmptyMessage = () => {
    if (activeFilter === "unread") return "You're all caught up!";
    if (activeFilter === "all") return "No notifications yet";
    return `No ${activeFilter} notifications`;
  };

  return (
    <DashboardLayout>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl" style={{ color: "var(--page-heading)" }}>Notifications</h1>
            {unreadCount > 0 && (
              <Badge variant="info" dot>{unreadCount} unread</Badge>
            )}
          </div>
          <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>Stay up to date with your marketing activities</p>
        </div>
        {unreadCount > 0 && (
          <Button variant="secondary" icon={<CheckCheck className="w-4 h-4" />} onClick={markAllRead}>
            Mark All Read
          </Button>
        )}
      </motion.div>

      {/* Filter Tabs */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }} className="mb-6">
        <div
          className="flex items-center gap-1 p-1 rounded-xl overflow-x-auto"
          style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
        >
          {filterTabs.map((tab) => {
            const count = tab.id === "all"
              ? notifications.length
              : tab.id === "unread"
                ? unreadCount
                : notifications.filter((n) => n.type === tab.type).length;
            const active = activeFilter === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => { setActiveFilter(tab.id); setPage(1); }}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 whitespace-nowrap cursor-pointer"
                style={active
                  ? { background: "rgba(124,58,237,0.14)", border: "1px solid rgba(124,58,237,0.30)", color: "var(--page-heading)" }
                  : { border: "1px solid transparent", color: "var(--page-text-muted)" }}
              >
                {tab.label}
                {count > 0 && (
                  <span
                    className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold tabular-nums"
                    style={active
                      ? { background: "rgba(124,58,237,0.25)", color: "#a78bfa" }
                      : { background: "var(--surface-border)", color: "var(--page-text-muted)" }}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Notification List */}
      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {paginated.length === 0 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <GlassCard>
                <EmptyState
                  icon={<BellOff className="w-7 h-7" />}
                  title={getEmptyMessage()}
                  description={activeFilter === "unread" ? "All notifications have been read." : "New notifications will appear here when there is activity."}
                />
              </GlassCard>
            </motion.div>
          ) : (
            paginated.map((notif, idx) => {
              const Icon = notif.icon;
              return (
                <motion.div
                  key={notif.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -100 }}
                  transition={{ delay: idx * 0.03, duration: 0.3 }}
                  onMouseEnter={() => setHoveredId(notif.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => markAsRead(notif.id)}
                  className="cursor-pointer"
                >
                  <div
                    className="relative flex items-start gap-4 p-4 rounded-2xl border transition-all duration-200 hover:shadow-[var(--surface-shadow-hover)]"
                    style={{
                      backgroundColor: notif.read ? "var(--surface-bg)" : "rgba(124,58,237,0.05)",
                      borderColor: "var(--surface-border)",
                      borderLeft: notif.read ? "1px solid var(--surface-border)" : "2px solid #7c3aed",
                    }}
                  >
                    {/* Unread dot */}
                    {!notif.read && (
                      <div className="absolute top-4 right-4 w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: "#7c3aed" }} />
                    )}

                    {/* Icon */}
                    <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0", notif.iconBg)}>
                      <Icon className={cn("w-5 h-5", notif.iconColor)} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm font-medium" style={{ color: notif.read ? "var(--page-text)" : "var(--page-heading)" }}>
                            {notif.title}
                          </p>
                          <p className="text-sm mt-0.5 leading-relaxed" style={{ color: "var(--page-text-secondary)" }}>{notif.message}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>{notif.time}</span>
                        <Badge variant="default" size="sm" className="capitalize">{notif.type}</Badge>
                      </div>
                    </div>

                    {/* Delete on hover */}
                    <AnimatePresence>
                      {hoveredId === notif.id && (
                        <motion.button
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.8 }}
                          transition={{ duration: 0.15 }}
                          onClick={(e) => { e.stopPropagation(); deleteNotification(notif.id); }}
                          className="absolute top-4 right-4 p-1.5 rounded-lg transition-colors cursor-pointer hover:text-red-400 hover:bg-red-500/10"
                          style={{ color: "var(--page-text-muted)" }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </motion.button>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="flex items-center justify-center gap-2 mt-8">
          <Button
            variant="ghost"
            size="sm"
            icon={<ChevronLeft className="w-4 h-4" />}
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className="w-8 h-8 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer tabular-nums"
                style={p === page
                  ? { background: "rgba(124,58,237,0.14)", border: "1px solid rgba(124,58,237,0.30)", color: "var(--page-heading)" }
                  : { border: "1px solid transparent", color: "var(--page-text-muted)" }}
              >
                {p}
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={<ChevronRight className="w-4 h-4" />}
            iconPosition="right"
            disabled={page === totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </Button>
        </motion.div>
      )}
    </DashboardLayout>
  );
}
