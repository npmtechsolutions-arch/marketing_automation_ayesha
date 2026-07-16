import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  CalendarDays,
  Plus,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Clock,
  Eye,
  Heart,
  MessageCircle,
  Share2,
  Pencil,
  Trash2,
  RefreshCw,
  Copy,
  Image as ImageIcon,
  TrendingUp,
  Music2,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import PlatformIcon from "@/components/shared/PlatformIcon";
import { cn, formatDate, getPlatformColor } from "@/lib/utils";
import api from "@/lib/api";

// ---------- Types ----------
type Platform = "facebook" | "instagram" | "linkedin" | "twitter" | "youtube";
type PostStatus = "published" | "scheduled" | "draft" | "failed" | "publishing";
type CalendarView = "week" | "month";

interface CalendarPost {
  id: string;
  title: string;
  content: string;
  platform: Platform;
  status: PostStatus;
  date: Date;
  hour?: number;
  minute?: number;
  durationHours?: number;
  imageUrl?: string;
  engagement?: {
    likes: number;
    comments: number;
    shares: number;
    views: number;
  };
  instagramMusicTrack?: string | null;
  instagramPostType?: "post" | "reel" | null;
}

// ---------- Constants ----------
const PLATFORMS: { key: Platform | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "facebook", label: "Facebook" },
  { key: "instagram", label: "Instagram" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "twitter", label: "Twitter" },
  { key: "youtube", label: "YouTube" },
];

const STATUS_FILTERS: { key: PostStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "published", label: "Published" },
  { key: "scheduled", label: "Scheduled" },
  { key: "draft", label: "Drafts" },
  { key: "failed", label: "Failed" },
];

const STATUS_CHIP_STYLES: Record<PostStatus, string> = {
  published: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  scheduled: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  draft: "bg-slate-500/20 text-slate-300 border-slate-500/30",
  failed: "bg-red-500/20 text-red-300 border-red-500/30",
  publishing: "bg-purple-500/20 text-purple-300 border-purple-500/30 animate-pulse",
};

const STATUS_DOT_COLORS: Record<PostStatus, string> = {
  published: "bg-emerald-400",
  scheduled: "bg-blue-400",
  draft: "bg-slate-400",
  failed: "bg-red-400",
  publishing: "bg-purple-400",
};

const STATUS_BADGE_VARIANT: Record<PostStatus, "success" | "info" | "default" | "danger" | "warning"> = {
  published: "success",
  scheduled: "info",
  draft: "default",
  failed: "danger",
  publishing: "warning",
};

const PLATFORM_LABELS: Record<Platform, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  linkedin: "LinkedIn",
  twitter: "Twitter",
  youtube: "YouTube",
};

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOURS = Array.from({ length: 13 }, (_, i) => i + 8); // 8 AM - 8 PM


// ---------- Helpers ----------
function getMonthDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevMonthDays = new Date(year, month, 0).getDate();

  const cells: {
    date: number;
    month: number;
    year: number;
    isCurrentMonth: boolean;
  }[] = [];

  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({
      date: prevMonthDays - i,
      month: month - 1,
      year,
      isCurrentMonth: false,
    });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ date: d, month, year, isCurrentMonth: true });
  }
  const remainder = cells.length % 7;
  if (remainder > 0) {
    for (let i = 1; i <= 7 - remainder; i++) {
      cells.push({
        date: i,
        month: month + 1,
        year,
        isCurrentMonth: false,
      });
    }
  }
  return cells;
}

function getWeekDays(baseDate: Date) {
  const startOfWeek = new Date(baseDate);
  startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(d.getDate() + i);
    return d;
  });
}

function isSameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatHour(hour: number): string {
  if (hour === 0) return "12 AM";
  if (hour === 12) return "12 PM";
  return hour > 12 ? `${hour - 12} PM` : `${hour} AM`;
}

function formatTime(hour: number, minute: number): string {
  const ampm = hour >= 12 ? "PM" : "AM";
  const h = hour % 12 || 12;
  const m = String(minute).padStart(2, "0");
  return `${h}:${m} ${ampm}`;
}

// ---------- Sub-components ----------
function PostChip({
  post,
  compact = false,
  onClick,
}: {
  post: CalendarPost;
  compact?: boolean;
  onClick: () => void;
}) {
  const platformColor = getPlatformColor(post.platform);

  return (
    <motion.button
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "w-full text-left rounded-md border transition-all duration-150 flex items-center gap-1.5 group/chip",
        STATUS_CHIP_STYLES[post.status],
        compact ? "px-1 py-0.5" : "px-1.5 py-1"
      )}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: platformColor }}
      />
      <span
        className={cn(
          "truncate font-medium leading-tight",
          compact ? "text-[9px]" : "text-[10px]"
        )}
      >
        {post.title}
      </span>
    </motion.button>
  );
}

function CurrentTimeIndicator() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  const hours = now.getHours();
  const minutes = now.getMinutes();

  if (hours < 8 || hours > 20) return null;

  const topPercent = ((hours - 8) * 60 + minutes) / (13 * 60);

  return (
    <div
      className="absolute left-0 right-0 z-20 pointer-events-none"
      style={{ top: `${topPercent * 100}%` }}
    >
      <div className="relative flex items-center">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500 -ml-1 shadow-lg shadow-red-500/50" />
        <div className="flex-1 h-[2px] bg-gradient-to-r from-red-500 to-red-500/0" />
      </div>
    </div>
  );
}

function EngagementMetric({
  icon,
  label,
  value,
  delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="text-center p-3 rounded-xl bg-white/5 border border-white/10 hover:bg-white/[0.08] transition-colors"
    >
      <div className="flex justify-center text-gray-400 mb-1.5">{icon}</div>
      <div className="text-lg font-bold text-white">
        {value.toLocaleString()}
      </div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">
        {label}
      </div>
    </motion.div>
  );
}

// ---------- Main Component ----------
// Map backend status strings to CalendarPost status
function mapStatus(backendStatus: string): PostStatus {
  const s = backendStatus.toLowerCase();
  if (s === "published" || s === "partially_published") return "published";
  if (s === "scheduled") return "scheduled";
  if (s === "failed") return "failed";
  if (s === "publishing") return "publishing";
  return "draft";
}

// Map platform name to Platform type
function mapPlatform(name: string): Platform {
  const n = (name || "").toLowerCase();
  if (n.includes("instagram")) return "instagram";
  if (n.includes("facebook")) return "facebook";
  if (n.includes("linkedin")) return "linkedin";
  if (n.includes("twitter") || n.includes("x")) return "twitter";
  if (n.includes("youtube")) return "youtube";
  return "instagram";
}

export default function CalendarPage() {
  const [view, setView] = useState<CalendarView>("month");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [platformFilter, setPlatformFilter] = useState<Platform | "all">("all");
  const [statusFilter, setStatusFilter] = useState<PostStatus | "all">("all");
  const [selectedPost, setSelectedPost] = useState<CalendarPost | null>(null);
  const handlePostClick = async (post: CalendarPost) => {
    setSelectedPost(post);
    const accountId = localStorage.getItem("account_id");
    if (!accountId) return;
    try {
      const res: any = await api.get(`/accounts/${accountId}/posts/${post.id}`);
      const p = res.data;
      if (p) {
        const updatedPost: CalendarPost = {
          ...post,
          status: mapStatus(p.status),
          engagement: {
            likes: p.performance?.likes ?? 0,
            comments: p.performance?.comments ?? 0,
            shares: p.performance?.shares ?? 0,
            views: p.performance?.views ?? 0,
          },
        };
        setSelectedPost(updatedPost);
        setPosts((prev) =>
          prev.map((item) => (item.id === post.id ? updatedPost : item))
        );
      }
    } catch (err) {
      console.error("Failed to sync post details:", err);
    }
  };
  const [navDirection, setNavDirection] = useState<1 | -1>(1);
  const weekScrollRef = useRef<HTMLDivElement>(null);
  const [posts, setPosts] = useState<CalendarPost[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const today = new Date();

  const fetchPosts = useCallback(async () => {
    const accountId = localStorage.getItem("account_id");
    if (!accountId) return;
    setIsLoading(true);
    try {
      const res: any = await api.get(`/accounts/${accountId}/posts/?per_page=100`);
      const items = res.data?.items ?? res.data ?? [];
      const mapped: CalendarPost[] = items.map((p: any) => {
        // Determine platform from target_accounts or fallback
        const firstTarget = p.target_accounts?.[0];
        const platformName = firstTarget?.platform_name ?? "Instagram";
        const platform = mapPlatform(platformName);

        // Determine date from scheduled_at, published_at, or created_at
        const rawDate = p.scheduled_at ?? p.published_at ?? p.created_at;
        const date = rawDate ? new Date(rawDate) : new Date();

        return {
          id: p.id,
          title: p.title || p.content?.slice(0, 40) || "Untitled Post",
          content: p.content || "",
          platform,
          status: mapStatus(p.status),
          date,
          hour: date.getHours(),
          minute: date.getMinutes(),
          imageUrl: Array.isArray(p.media_urls) && p.media_urls[0]
            ? (p.media_urls[0].startsWith("data:") ? undefined : p.media_urls[0])
            : undefined,
          engagement: {
            likes: p.performance?.likes ?? 0,
            comments: p.performance?.comments ?? 0,
            shares: p.performance?.shares ?? 0,
            views: p.performance?.views ?? 0,
          },
          instagramMusicTrack: p.instagram_music_track,
          instagramPostType: p.instagram_post_type,
        } as CalendarPost;
      });
      setPosts(mapped);
    } catch (err) {
      console.error("Failed to fetch calendar posts:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPosts();
  }, [fetchPosts]);

  const filteredPosts = useMemo(() => {
    return posts.filter((p) => {
      if (platformFilter !== "all" && p.platform !== platformFilter) return false;
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      return true;
    });
  }, [posts, platformFilter, statusFilter]);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthName = currentDate.toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  // Stats
  const publishedCount = filteredPosts.filter((p) => p.status === "published").length;
  const scheduledCount = filteredPosts.filter((p) => p.status === "scheduled").length;
  const draftCount = filteredPosts.filter((p) => p.status === "draft").length;
  const failedCount = filteredPosts.filter((p) => p.status === "failed").length;

  const navigateMonth = (dir: 1 | -1) => {
    setNavDirection(dir);
    setCurrentDate(new Date(year, month + dir, 1));
  };

  const navigateWeek = (dir: 1 | -1) => {
    setNavDirection(dir);
    const d = new Date(currentDate);
    d.setDate(d.getDate() + dir * 7);
    setCurrentDate(d);
  };

  const goToToday = () => {
    setNavDirection(1);
    setCurrentDate(new Date());
  };

  const monthCells = useMemo(() => getMonthDays(year, month), [year, month]);
  const weekDays = useMemo(() => getWeekDays(currentDate), [currentDate]);

  function postsForDay(date: number, m: number, y: number) {
    return filteredPosts.filter(
      (p) =>
        p.date.getDate() === date &&
        p.date.getMonth() === m &&
        p.date.getFullYear() === y
    );
  }

  function postsForDayDate(d: Date) {
    return filteredPosts.filter((p) => isSameDay(p.date, d));
  }

  // Scroll to current time in week view
  useEffect(() => {
    if (view === "week" && weekScrollRef.current) {
      const now = new Date();
      const hour = now.getHours();
      if (hour >= 8 && hour <= 20) {
        const scrollPosition = ((hour - 8) / 13) * weekScrollRef.current.scrollHeight;
        weekScrollRef.current.scrollTo({ top: scrollPosition - 100, behavior: "smooth" });
      }
    }
  }, [view]);

  // ---------- Render ----------
  return (
    <DashboardLayout>
      <div className="space-y-6 pb-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/20 shadow-lg shadow-purple-500/10">
              <CalendarDays className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Content Calendar
              </h1>
              <p className="text-sm text-gray-400">
                Plan and schedule your content across platforms
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* View toggle */}
            <div className="flex items-center p-1 rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm">
              {(["week", "month"] as CalendarView[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={cn(
                    "relative px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 capitalize",
                    view === v
                      ? "text-white"
                      : "text-gray-400 hover:text-white"
                  )}
                >
                  {view === v && (
                    <motion.div
                      layoutId="viewToggle"
                      className="absolute inset-0 rounded-lg bg-gradient-to-r from-purple-600/30 to-blue-600/30 border border-purple-500/30"
                      transition={{ type: "spring", duration: 0.4 }}
                    />
                  )}
                  <span className="relative z-10">{v}</span>
                </button>
              ))}
            </div>

            <Button
              variant="secondary"
              icon={<Sparkles className="w-4 h-4" />}
            >
              Auto Schedule
            </Button>
            <Button
              variant="secondary"
              icon={<RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />}
              onClick={fetchPosts}
              disabled={isLoading}
            >
              Refresh
            </Button>
            <Button
              icon={<Plus className="w-4 h-4" />}
              onClick={() => navigate("/create-post")}
            >
              New Post
            </Button>
          </div>
        </motion.div>

        {/* Quick stats */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-3"
        >
          {[
            {
              label: "Published",
              count: publishedCount,
              color: "emerald",
              dotColor: "bg-emerald-400",
            },
            {
              label: "Scheduled",
              count: scheduledCount,
              color: "blue",
              dotColor: "bg-blue-400",
            },
            {
              label: "Drafts",
              count: draftCount,
              color: "slate",
              dotColor: "bg-slate-400",
            },
            {
              label: "Failed",
              count: failedCount,
              color: "red",
              dotColor: "bg-red-400",
            },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 + i * 0.05 }}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.06] backdrop-blur-sm"
            >
              <div className={cn("w-2 h-2 rounded-full", stat.dotColor)} />
              <div>
                {isLoading ? (
                  <span className="inline-block w-8 h-5 rounded bg-white/10 animate-pulse" />
                ) : (
                  <span className="text-lg font-bold text-white">
                    {stat.count}
                  </span>
                )}
                <span className="text-xs text-gray-500 ml-2">
                  {stat.label}
                </span>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Filter Bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          {/* Platform filters */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            {PLATFORMS.map((p) => (
              <motion.button
                key={p.key}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() =>
                  setPlatformFilter(p.key as Platform | "all")
                }
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 whitespace-nowrap flex-shrink-0",
                  platformFilter === p.key
                    ? "bg-purple-500/20 border-purple-500/30 text-purple-300 shadow-sm shadow-purple-500/10"
                    : "bg-white/5 border-white/10 text-gray-400 hover:text-white hover:border-white/20"
                )}
              >
                {p.key !== "all" && (
                  <PlatformIcon
                    platform={p.key as Platform}
                    size="sm"
                  />
                )}
                {p.label}
              </motion.button>
            ))}
          </div>

          {/* Status filters */}
          <div className="flex items-center gap-2 flex-wrap">
            {STATUS_FILTERS.map((s) => (
              <motion.button
                key={s.key}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() =>
                  setStatusFilter(s.key as PostStatus | "all")
                }
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200",
                  statusFilter === s.key
                    ? "bg-purple-500/20 border-purple-500/30 text-purple-300 shadow-sm shadow-purple-500/10"
                    : "bg-white/5 border-white/10 text-gray-400 hover:text-white hover:border-white/20"
                )}
              >
                {s.key !== "all" && (
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      STATUS_DOT_COLORS[s.key as PostStatus]
                    )}
                  />
                )}
                {s.label}
              </motion.button>
            ))}
          </div>
        </motion.div>

        {/* Calendar Card */}
        <GlassCard padding="sm">
          {/* Navigation */}
          <div className="flex items-center justify-between mb-4 px-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  view === "month" ? navigateMonth(-1) : navigateWeek(-1)
                }
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-all duration-200"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <button
                onClick={() =>
                  view === "month" ? navigateMonth(1) : navigateWeek(1)
                }
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-all duration-200"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            <h2 className="text-lg font-semibold text-white">
              {view === "month"
                ? monthName
                : `${weekDays[0].toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })} - ${weekDays[6].toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}`}
            </h2>

            <button
              onClick={goToToday}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-purple-300 bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 transition-all duration-200"
            >
              Today
            </button>
          </div>

          {/* Calendar content */}
          <AnimatePresence mode="wait">
            {view === "month" ? (
              /* ==================== MONTH VIEW ==================== */
              <motion.div
                key={`month-${year}-${month}`}
                initial={{ opacity: 0, x: navDirection * 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: navDirection * -40 }}
                transition={{ duration: 0.3, ease: "easeInOut" }}
              >
                {/* Day headers */}
                <div className="grid grid-cols-7 gap-1 mb-1">
                  {DAY_NAMES.map((d) => (
                    <div
                      key={d}
                      className="text-center text-[11px] font-semibold text-gray-500 uppercase tracking-wider py-2"
                    >
                      {d}
                    </div>
                  ))}
                </div>

                {/* Day cells */}
                <div className="grid grid-cols-7 gap-1">
                  {monthCells.map((cell, idx) => {
                    const isToday =
                      cell.isCurrentMonth &&
                      cell.date === today.getDate() &&
                      month === today.getMonth() &&
                      year === today.getFullYear();
                    const dayPosts = postsForDay(
                      cell.date,
                      cell.month,
                      cell.year
                    );

                    return (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: idx * 0.008 }}
                        onClick={() => {
                          if (cell.isCurrentMonth) {
                            const dateStr = `${cell.year}-${String(cell.month + 1).padStart(2, "0")}-${String(cell.date).padStart(2, "0")}`;
                            navigate(`/create-post?date=${dateStr}`);
                          }
                        }}
                        className={cn(
                          "relative min-h-[120px] rounded-lg p-2 border transition-all duration-200 cursor-pointer group",
                          cell.isCurrentMonth
                            ? "bg-white/[0.03] border-white/[0.05] hover:bg-white/[0.08] hover:border-white/[0.12]"
                            : "bg-transparent border-transparent opacity-40",
                          isToday &&
                            "ring-2 ring-purple-500 bg-purple-500/10 border-purple-500/20"
                        )}
                      >
                        {/* Date number */}
                        <div className="flex items-center justify-between mb-1">
                          <span
                            className={cn(
                              "text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full",
                              isToday
                                ? "bg-purple-500 text-white"
                                : cell.isCurrentMonth
                                  ? "text-gray-400 group-hover:text-gray-300"
                                  : "text-gray-600"
                            )}
                          >
                            {cell.date}
                          </span>
                          {dayPosts.length > 0 && (
                            <span className="text-[9px] text-gray-600 font-medium">
                              {dayPosts.length}
                            </span>
                          )}
                        </div>

                        {/* Post chips */}
                        <div className="space-y-1">
                          {dayPosts.slice(0, 3).map((post) => (
                            <PostChip
                              key={post.id}
                              post={post}
                              compact={dayPosts.length > 2}
                              onClick={() => handlePostClick(post)}
                            />
                          ))}
                          {dayPosts.length > 3 && (
                            <span className="block text-[9px] text-gray-500 pl-1 font-medium">
                              +{dayPosts.length - 3} more
                            </span>
                          )}
                        </div>

                        {/* Hover overlay for empty cells */}
                        {dayPosts.length === 0 && cell.isCurrentMonth && (
                          <div className="absolute inset-0 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            <Plus className="w-5 h-5 text-gray-600" />
                          </div>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            ) : (
              /* ==================== WEEK VIEW ==================== */
              <motion.div
                key={`week-${weekDays[0].toISOString()}`}
                initial={{ opacity: 0, x: navDirection * 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: navDirection * -40 }}
                transition={{ duration: 0.3, ease: "easeInOut" }}
              >
                {/* Day headers */}
                <div className="grid grid-cols-[56px_repeat(7,1fr)] gap-1 mb-1">
                  <div />
                  {weekDays.map((d, i) => {
                    const isToday_ = isSameDay(d, today);
                    const dayPosts = postsForDayDate(d);
                    return (
                      <div
                        key={i}
                        className={cn(
                          "text-center py-2.5 rounded-lg transition-colors",
                          isToday_ && "bg-purple-500/10 border border-purple-500/20"
                        )}
                      >
                        <div className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
                          {DAY_NAMES[d.getDay()]}
                        </div>
                        <div
                          className={cn(
                            "text-lg font-bold mt-0.5",
                            isToday_ ? "text-purple-300" : "text-white"
                          )}
                        >
                          {d.getDate()}
                        </div>
                        {dayPosts.length > 0 && (
                          <div className="flex justify-center gap-0.5 mt-1">
                            {dayPosts.slice(0, 4).map((p) => (
                              <div
                                key={p.id}
                                className={cn(
                                  "w-1 h-1 rounded-full",
                                  STATUS_DOT_COLORS[p.status]
                                )}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Time grid */}
                <div
                  ref={weekScrollRef}
                  className="relative max-h-[520px] overflow-y-auto custom-scrollbar"
                >
                  {/* Current time indicator */}
                  <div className="absolute inset-0 pointer-events-none">
                    <div className="grid grid-cols-[56px_repeat(7,1fr)] gap-1 h-full">
                      <div />
                      {weekDays.map((d, i) => (
                        <div key={i} className="relative">
                          {isSameDay(d, today) && <CurrentTimeIndicator />}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Hour rows */}
                  <div className="grid grid-cols-[56px_repeat(7,1fr)] gap-1">
                    {HOURS.map((hour) => (
                      <div key={hour} className="contents">
                        <div className="text-[10px] text-gray-500 text-right pr-2 py-4 font-medium">
                          {formatHour(hour)}
                        </div>
                        {weekDays.map((d, dayIdx) => {
                          const hourPosts = postsForDayDate(d).filter(
                            (p) => p.hour === hour
                          );
                          return (
                            <div
                              key={dayIdx}
                              className={cn(
                                "border border-white/[0.04] rounded-lg min-h-[52px] p-0.5 hover:bg-white/[0.04] transition-colors relative",
                                isSameDay(d, today) && "bg-purple-500/[0.02]"
                              )}
                            >
                              {hourPosts.map((post) => {
                                const spanHeight = (post.durationHours || 1) * 100;
                                return (
                                  <motion.button
                                    key={post.id}
                                    whileHover={{ scale: 1.02 }}
                                    onClick={() => handlePostClick(post)}
                                    className={cn(
                                      "w-full text-left px-2 py-1.5 rounded-md text-[10px] font-medium border mb-0.5 transition-all",
                                      STATUS_CHIP_STYLES[post.status],
                                      "hover:brightness-125"
                                    )}
                                    style={
                                      spanHeight > 100
                                        ? {
                                            minHeight: `${spanHeight}%`,
                                            position: "relative",
                                            zIndex: 10,
                                          }
                                        : undefined
                                    }
                                  >
                                    <div className="flex items-center gap-1">
                                      <PlatformIcon
                                        platform={post.platform}
                                        size="sm"
                                      />
                                      <span className="truncate">
                                        {post.title}
                                      </span>
                                    </div>
                                    <div className="text-[8px] opacity-60 mt-0.5">
                                      {formatTime(post.hour ?? hour, post.minute ?? 0)}
                                    </div>
                                  </motion.button>
                                );
                              })}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </GlassCard>
      </div>

      {/* ==================== POST PREVIEW MODAL ==================== */}
      <Modal
        isOpen={!!selectedPost}
        onClose={() => setSelectedPost(null)}
        title="Post Details"
        size="lg"
      >
        {selectedPost && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-5"
          >
            {/* Status & Platform row */}
            <div className="flex items-center gap-3 flex-wrap">
              <Badge
                variant={STATUS_BADGE_VARIANT[selectedPost.status]}
                dot
              >
                {selectedPost.status.charAt(0).toUpperCase() +
                  selectedPost.status.slice(1)}
              </Badge>
              <Badge variant="platform" platform={selectedPost.platform}>
                <span className="flex items-center gap-1.5">
                  <PlatformIcon
                    platform={selectedPost.platform}
                    size="sm"
                  />
                  {PLATFORM_LABELS[selectedPost.platform]}
                </span>
              </Badge>
              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                <Clock className="w-3.5 h-3.5" />
                {formatDate(selectedPost.date)}
                {selectedPost.hour !== undefined &&
                  ` at ${formatTime(selectedPost.hour, selectedPost.minute ?? 0)}`}
              </span>
            </div>

            {/* Title */}
            <h3 className="text-lg font-semibold text-white">
              {selectedPost.title}
            </h3>

            {/* Media Preview */}
            {selectedPost.imageUrl && (
              <div className="w-full h-48 rounded-xl overflow-hidden border border-white/10 bg-black/20 flex items-center justify-center">
                <img
                  src={selectedPost.imageUrl}
                  alt={selectedPost.title || "Post media preview"}
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Audio/Music Track */}
            {selectedPost.instagramMusicTrack && (
              <div className="flex items-center gap-2.5 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300">
                <Music2 className="w-4 h-4 animate-pulse flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-purple-400 font-semibold truncate">
                    ♫ {selectedPost.instagramMusicTrack.split(" – ")[0]}
                  </p>
                  {selectedPost.instagramMusicTrack.split(" – ")[1] && (
                    <p className="text-[10px] text-gray-400 truncate">
                      Artist: {selectedPost.instagramMusicTrack.split(" – ")[1]}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Content */}
            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                {selectedPost.content}
              </p>
            </div>

            {/* Engagement metrics (published only) */}
            {selectedPost.status === "published" &&
              selectedPost.engagement && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-medium text-white">
                      Engagement
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-3">
                    <EngagementMetric
                      icon={<Eye className="w-4 h-4" />}
                      label="Views"
                      value={selectedPost.engagement.views}
                      delay={0.1}
                    />
                    <EngagementMetric
                      icon={<Heart className="w-4 h-4" />}
                      label="Likes"
                      value={selectedPost.engagement.likes}
                      delay={0.15}
                    />
                    <EngagementMetric
                      icon={<MessageCircle className="w-4 h-4" />}
                      label="Comments"
                      value={selectedPost.engagement.comments}
                      delay={0.2}
                    />
                    <EngagementMetric
                      icon={<Share2 className="w-4 h-4" />}
                      label="Shares"
                      value={selectedPost.engagement.shares}
                      delay={0.25}
                    />
                  </div>
                </div>
              )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-3 border-t border-white/10">
              <Button
                variant="secondary"
                icon={<Pencil className="w-4 h-4" />}
                size="sm"
              >
                Edit
              </Button>
              <Button
                variant="secondary"
                icon={<Copy className="w-4 h-4" />}
                size="sm"
              >
                Duplicate
              </Button>
              <Button
                variant="secondary"
                icon={<RefreshCw className="w-4 h-4" />}
                size="sm"
              >
                Reschedule
              </Button>
              {(selectedPost.status === "draft" ||
                selectedPost.status === "scheduled") && (
                <Button
                  variant="danger"
                  icon={<Trash2 className="w-4 h-4" />}
                  size="sm"
                >
                  Delete
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </Modal>
    </DashboardLayout>
  );
}
