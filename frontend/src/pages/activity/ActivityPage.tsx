import { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  PenSquare,
  Share2,
  Users,
  Sparkles,
  Lightbulb,
  CreditCard,
  Shield,
  Settings,
  Filter,
  ChevronDown,
  Loader2,
  FileText,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn, formatDate, formatRelativeTime } from "@/lib/utils";
import api from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

type ActivityCategory =
  | "post"
  | "platform"
  | "account"
  | "ai"
  | "strategy"
  | "billing"
  | "auth"
  | "settings";

type ActivityStatus = "success" | "failed" | "warning";

interface ActivityEntry {
  id: string;
  category: ActivityCategory;
  action: string;
  description: string;
  resource_name?: string;
  status: ActivityStatus;
  created_at: string;
}

/* ------------------------------------------------------------------ */
/*  Category config                                                   */
/* ------------------------------------------------------------------ */

const categoryConfig: Record<
  ActivityCategory,
  { icon: typeof PenSquare; color: string; bgColor: string; dotColor: string; label: string }
> = {
  post: {
    icon: PenSquare,
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
    dotColor: "bg-purple-400",
    label: "Posts",
  },
  platform: {
    icon: Share2,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    dotColor: "bg-blue-400",
    label: "Platforms",
  },
  account: {
    icon: Users,
    color: "text-green-400",
    bgColor: "bg-green-500/10",
    dotColor: "bg-green-400",
    label: "Accounts",
  },
  ai: {
    icon: Sparkles,
    color: "text-pink-400",
    bgColor: "bg-pink-500/10",
    dotColor: "bg-pink-400",
    label: "AI",
  },
  strategy: {
    icon: Lightbulb,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    dotColor: "bg-amber-400",
    label: "Strategy",
  },
  billing: {
    icon: CreditCard,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    dotColor: "bg-emerald-400",
    label: "Billing",
  },
  auth: {
    icon: Shield,
    color: "text-slate-400",
    bgColor: "bg-slate-500/10",
    dotColor: "bg-slate-400",
    label: "Auth",
  },
  settings: {
    icon: Settings,
    color: "text-gray-400",
    bgColor: "bg-gray-500/10",
    dotColor: "bg-gray-400",
    label: "Settings",
  },
};

const statusBadgeVariant: Record<ActivityStatus, "success" | "danger" | "warning"> = {
  success: "success",
  failed: "danger",
  warning: "warning",
};

/* ------------------------------------------------------------------ */
/*  Filter constants                                                  */
/* ------------------------------------------------------------------ */

const categoryFilters: { value: string; label: string }[] = [
  { value: "all", label: "All" },
  { value: "post", label: "Posts" },
  { value: "platform", label: "Platforms" },
  { value: "account", label: "Accounts" },
  { value: "ai", label: "AI" },
  { value: "strategy", label: "Strategy" },
  { value: "billing", label: "Billing" },
  { value: "auth", label: "Auth" },
  { value: "settings", label: "Settings" },
];

const dateFilters = ["Today", "This Week", "This Month", "Custom"] as const;
const statusFilters = ["All", "Success", "Failed"] as const;

/* ------------------------------------------------------------------ */
/*  Stat helpers                                                      */
/* ------------------------------------------------------------------ */

function getStats(activities: ActivityEntry[]) {
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayItems = activities.filter((a) => new Date(a.created_at) >= todayStart);

  return {
    totalToday: todayItems.length,
    postsCreated: activities.filter((a) => a.category === "post").length,
    aiGenerations: activities.filter((a) => a.category === "ai").length,
    accountsConnected: activities.filter(
      (a) => a.category === "account" || a.category === "platform"
    ).length,
  };
}

/* ------------------------------------------------------------------ */
/*  Component: StatCard                                               */
/* ------------------------------------------------------------------ */

function ActivityStatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <GlassCard padding="sm" className="flex-1 min-w-[140px]">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={cn("text-2xl font-bold", color)}>{value}</p>
    </GlassCard>
  );
}

/* ------------------------------------------------------------------ */
/*  Component: Timeline Entry                                         */
/* ------------------------------------------------------------------ */

function TimelineEntry({ entry, isLast }: { entry: ActivityEntry; isLast: boolean }) {
  const config = categoryConfig[entry.category];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="relative flex gap-4 pb-8 last:pb-0"
    >
      {/* Timeline line + dot */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-slate-800",
            config.bgColor
          )}
        >
          <div className={cn("h-3 w-3 rounded-full", config.dotColor)} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 bg-gradient-to-b from-white/10 to-transparent" />
        )}
      </div>

      {/* Timestamp - shown above card on mobile, to the side on desktop */}
      <div className="flex-1 min-w-0">
        {/* Timestamp */}
        <div className="mb-1.5 flex items-center gap-2">
          <span
            className="text-xs text-slate-500 cursor-default"
            title={formatDate(entry.created_at)}
          >
            {formatRelativeTime(entry.created_at)}
          </span>
        </div>

        {/* Activity card */}
        <GlassCard padding="sm" className="group">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                config.bgColor
              )}
            >
              <Icon className={cn("h-4 w-4", config.color)} />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h4 className="text-sm font-semibold text-white">{entry.action}</h4>
                <Badge
                  variant={statusBadgeVariant[entry.status]}
                  size="sm"
                  dot
                >
                  {entry.status.charAt(0).toUpperCase() + entry.status.slice(1)}
                </Badge>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                {entry.description}
              </p>

              {entry.resource_name && (
                <div className="mt-2">
                  <Badge variant="default" size="sm">
                    <FileText className="h-3 w-3 mr-1" />
                    {entry.resource_name}
                  </Badge>
                </div>
              )}
            </div>
          </div>
        </GlassCard>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                         */
/* ------------------------------------------------------------------ */

export default function ActivityPage() {
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState<(typeof dateFilters)[number]>("This Month");
  const [statusFilter, setStatusFilter] = useState<(typeof statusFilters)[number]>("All");
  const [visibleCount, setVisibleCount] = useState(10);
  const [dateDropdownOpen, setDateDropdownOpen] = useState(false);
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const accountId = localStorage.getItem("account_id");

  useEffect(() => {
    if (!accountId) { setLoading(false); return; }
    api.get(`/accounts/${accountId}/activity/?limit=100`)
      .then((res: any) => {
        const payload = res.data || res;
        const items = payload.items || payload || [];
        const mapped: ActivityEntry[] = items.map((a: any) => ({
          id: a.id,
          category: (a.activity_type || a.category || "settings") as ActivityCategory,
          action: a.action || a.title || "Action",
          description: a.description || a.message || "",
          resource_name: a.resource_name || a.resource_id || undefined,
          status: (a.status || "success") as ActivityStatus,
          created_at: a.created_at,
        }));
        setActivities(mapped);
      })
      .catch(() => setActivities([]))
      .finally(() => setLoading(false));
  }, [accountId]);

  const filtered = useMemo(() => {
    let items = activities;

    // Category filter
    if (categoryFilter !== "all") {
      items = items.filter((a) => a.category === categoryFilter);
    }

    // Status filter
    if (statusFilter !== "All") {
      items = items.filter(
        (a) => a.status === statusFilter.toLowerCase()
      );
    }

    // Date filter
    const nowDate = new Date();
    if (dateFilter === "Today") {
      const start = new Date(nowDate);
      start.setHours(0, 0, 0, 0);
      items = items.filter((a) => new Date(a.created_at) >= start);
    } else if (dateFilter === "This Week") {
      const start = new Date(nowDate);
      start.setDate(start.getDate() - start.getDay());
      start.setHours(0, 0, 0, 0);
      items = items.filter((a) => new Date(a.created_at) >= start);
    } else if (dateFilter === "This Month") {
      const start = new Date(nowDate.getFullYear(), nowDate.getMonth(), 1);
      items = items.filter((a) => new Date(a.created_at) >= start);
    }

    return items;
  }, [categoryFilter, statusFilter, dateFilter]);

  const visible = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;
  const stats = getStats(filtered);

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">Activity Log</h1>
          <p className="mt-1 text-sm text-slate-400">Your agency activity</p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ActivityStatCard label="Total Actions (Today)" value={stats.totalToday} color="text-white" />
          <ActivityStatCard label="Posts Created" value={stats.postsCreated} color="text-purple-400" />
          <ActivityStatCard label="AI Generations" value={stats.aiGenerations} color="text-pink-400" />
          <ActivityStatCard label="Accounts Connected" value={stats.accountsConnected} color="text-green-400" />
        </div>

        {/* Filter Bar */}
        <GlassCard padding="sm">
          <div className="space-y-3">
            {/* Category pills */}
            <div className="flex flex-wrap gap-2">
              {categoryFilters.map((cat) => (
                <button
                  key={cat.value}
                  onClick={() => setCategoryFilter(cat.value)}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-200",
                    categoryFilter === cat.value
                      ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                      : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10 hover:text-white"
                  )}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* Date + Status filters */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Filter className="h-3.5 w-3.5" />
                <span>Filters:</span>
              </div>

              {/* Date range dropdown */}
              <div className="relative">
                <button
                  onClick={() => {
                    setDateDropdownOpen(!dateDropdownOpen);
                    setStatusDropdownOpen(false);
                  }}
                  className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/10"
                >
                  {dateFilter}
                  <ChevronDown className={cn("h-3 w-3 transition-transform", dateDropdownOpen && "rotate-180")} />
                </button>
                <AnimatePresence>
                  {dateDropdownOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="absolute left-0 top-full z-50 mt-1 w-36 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 p-1 shadow-xl backdrop-blur-xl"
                    >
                      {dateFilters.map((d) => (
                        <button
                          key={d}
                          onClick={() => { setDateFilter(d); setDateDropdownOpen(false); }}
                          className={cn(
                            "w-full rounded-lg px-3 py-1.5 text-left text-xs transition-colors",
                            dateFilter === d
                              ? "bg-purple-500/15 text-purple-300"
                              : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                        >
                          {d}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Status dropdown */}
              <div className="relative">
                <button
                  onClick={() => {
                    setStatusDropdownOpen(!statusDropdownOpen);
                    setDateDropdownOpen(false);
                  }}
                  className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/10"
                >
                  Status: {statusFilter}
                  <ChevronDown className={cn("h-3 w-3 transition-transform", statusDropdownOpen && "rotate-180")} />
                </button>
                <AnimatePresence>
                  {statusDropdownOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="absolute left-0 top-full z-50 mt-1 w-32 overflow-hidden rounded-xl border border-white/10 bg-slate-900/95 p-1 shadow-xl backdrop-blur-xl"
                    >
                      {statusFilters.map((s) => (
                        <button
                          key={s}
                          onClick={() => { setStatusFilter(s); setStatusDropdownOpen(false); }}
                          className={cn(
                            "w-full rounded-lg px-3 py-1.5 text-left text-xs transition-colors",
                            statusFilter === s
                              ? "bg-purple-500/15 text-purple-300"
                              : "text-slate-300 hover:bg-white/10 hover:text-white"
                          )}
                        >
                          {s}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Timeline */}
        {visible.length > 0 ? (
          <div className="pl-1">
            {visible.map((entry, i) => (
              <TimelineEntry
                key={entry.id}
                entry={entry}
                isLast={i === visible.length - 1 && !hasMore}
              />
            ))}

            {/* Load More */}
            {hasMore && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Loader2 className="h-3.5 w-3.5" />}
                  onClick={() => setVisibleCount((c) => c + 10)}
                >
                  Load More
                </Button>
              </div>
            )}
          </div>
        ) : (
          /* Empty state */
          <GlassCard className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-white/5">
              <FileText className="h-8 w-8 text-slate-500" />
            </div>
            <h3 className="text-lg font-semibold text-white">No activities found</h3>
            <p className="mt-1 text-sm text-slate-400">
              Try adjusting your filters or check back later.
            </p>
          </GlassCard>
        )}
      </div>
    </DashboardLayout>
  );
}
