import { useState, useMemo } from "react";
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
/*  Mock data                                                         */
/* ------------------------------------------------------------------ */

const now = new Date();
function hoursAgo(h: number) {
  return new Date(now.getTime() - h * 3600_000).toISOString();
}

const mockActivities: ActivityEntry[] = [
  { id: "1", category: "post", action: "Post Published", description: "Published to 3 accounts: Acme Corp Instagram, TechStartup Pro IG, Acme Corp LinkedIn", resource_name: "Spring Campaign Launch", status: "success", created_at: hoursAgo(0.3) },
  { id: "2", category: "ai", action: "AI Caption Generated", description: "Generated 5 caption variations for upcoming product launch post", resource_name: "Product Launch Post", status: "success", created_at: hoursAgo(1) },
  { id: "3", category: "platform", action: "Platform Connected", description: "Successfully connected Instagram Business account", resource_name: "Instagram", status: "success", created_at: hoursAgo(2) },
  { id: "4", category: "post", action: "Post Scheduled", description: "Scheduled post for April 2, 2026 at 10:00 AM across 2 platforms", resource_name: "Weekly Tips #14", status: "success", created_at: hoursAgo(3) },
  { id: "5", category: "account", action: "Team Member Invited", description: "Invited sarah@acmecorp.com as Editor to the workspace", status: "success", created_at: hoursAgo(4) },
  { id: "6", category: "post", action: "Post Failed to Publish", description: "Failed to publish to TikTok: API rate limit exceeded. Will retry in 15 minutes.", resource_name: "Dance Challenge Promo", status: "failed", created_at: hoursAgo(5) },
  { id: "7", category: "strategy", action: "Strategy Report Generated", description: "Weekly performance strategy report generated with 12 actionable recommendations", resource_name: "Week 13 Strategy", status: "success", created_at: hoursAgo(6) },
  { id: "8", category: "billing", action: "Subscription Upgraded", description: "Upgraded from Pro to Business plan. New billing cycle starts April 1.", status: "success", created_at: hoursAgo(8) },
  { id: "9", category: "ai", action: "AI Image Generated", description: "Generated 4 image variations using AI for the brand awareness campaign", resource_name: "Brand Awareness Q2", status: "success", created_at: hoursAgo(10) },
  { id: "10", category: "auth", action: "Password Changed", description: "Account password was successfully updated", status: "success", created_at: hoursAgo(12) },
  { id: "11", category: "platform", action: "Platform Disconnected", description: "Twitter/X account disconnected due to expired token. Please reconnect.", resource_name: "Twitter/X", status: "warning", created_at: hoursAgo(18) },
  { id: "12", category: "post", action: "Bulk Posts Created", description: "Created 8 draft posts from CSV import for the next 2 weeks", status: "success", created_at: hoursAgo(24) },
  { id: "13", category: "settings", action: "Notification Preferences Updated", description: "Email notifications for post publishing turned on, SMS alerts turned off", status: "success", created_at: hoursAgo(26) },
  { id: "14", category: "account", action: "Social Account Added", description: "Connected Acme Corp LinkedIn company page with admin permissions", resource_name: "Acme Corp LinkedIn", status: "success", created_at: hoursAgo(30) },
  { id: "15", category: "ai", action: "AI Hashtag Suggestions", description: "Generated trending hashtag set for fitness niche with 25 hashtags", resource_name: "Fitness Hashtags", status: "success", created_at: hoursAgo(36) },
  { id: "16", category: "post", action: "Post Deleted", description: "Deleted draft post that was no longer relevant to the campaign", resource_name: "Old Promo Draft", status: "success", created_at: hoursAgo(40) },
  { id: "17", category: "strategy", action: "Competitor Analysis Run", description: "Analyzed 5 competitor accounts and identified 3 content gaps", status: "success", created_at: hoursAgo(48) },
  { id: "18", category: "billing", action: "Payment Failed", description: "Monthly payment of $49.00 failed. Please update your payment method.", status: "failed", created_at: hoursAgo(50) },
];

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

  const filtered = useMemo(() => {
    let items = [...mockActivities];

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
  const stats = getStats(mockActivities);

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
