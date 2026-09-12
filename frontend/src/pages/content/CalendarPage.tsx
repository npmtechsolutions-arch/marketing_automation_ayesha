import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  CalendarDays,
  ListChecks,
  FileSpreadsheet,
  Flame,
  Lightbulb,
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
  AlertTriangle,
  Send,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import PlatformIcon from "@/components/shared/PlatformIcon";
import PublishingJobs from "@/components/content/PublishingJobs";
import QueuePanel from "@/components/scheduling/QueuePanel";
import BulkImportDialog from "@/components/content/BulkImportDialog";
import BestTimesHeatmap from "@/components/scheduling/BestTimesHeatmap";
import CalendarSuggestions from "@/components/scheduling/CalendarSuggestions";
import ReviewPanel from "@/components/content/ReviewPanel";
import { statusMeta, type BadgeVariant, type ReviewStatus } from "@/lib/review";
import { wallClockDate } from "@/lib/scheduling";
import { STATUS_BUCKETS, bucketOf, isEditableDraft, mapStatus, type StatusBucket } from "@/lib/postStatus";
import { cn, formatDate, getPlatformColor } from "@/lib/utils";
import api, { getAccountId, getAccountIdSync } from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";
import { useAuthStore } from "@/stores/authStore";

// ---------- Types ----------
type Platform = "facebook" | "instagram" | "linkedin" | "twitter" | "youtube";
type PostStatus = ReviewStatus;
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
  errorMessage?: string | null;
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

// Buckets, not single statuses. Filtering on `status === "draft"` meant a post
// in review matched nothing and appeared under no filter at all; and "In review"
// and "Partly published" had no chip, so those posts were uncountable.
const STATUS_FILTERS: { key: StatusBucket | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "published", label: "Published" },
  { key: "partially_published", label: "Partly published" },
  { key: "scheduled", label: "Scheduled" },
  { key: "in_review", label: "In review" },
  { key: "draft", label: "Drafts" },
  { key: "failed", label: "Failed" },
];

// One hue per status, from the status tokens in index.css. The mapping is
// unchanged -- published is still green, failed still red, publishing still
// violet, and partially_published still amber and therefore still distinct
// from published. Only the shades move, because `text-emerald-300` on a 20%
// tint was drawn for a near-black background and washes out on a white card.
const chip = (name: string) =>
  `bg-[color:var(--status-${name}-bg)] text-[color:var(--status-${name}-fg)] ` +
  `border-[color:var(--status-${name}-border)]`;

const STATUS_CHIP_STYLES: Record<PostStatus, string> = {
  published: chip("published"),
  scheduled: chip("scheduled"),
  draft: chip("draft"),
  preview: chip("draft"),
  failed: chip("failed"),
  publishing: `${chip("publishing")} animate-pulse`,
  partially_published: chip("attention"),
  // Review states.
  pending_approval: chip("attention"),
  in_review: chip("attention"),
  changes_requested: chip("failed"),
  client_review: chip("scheduled"),
  approved: chip("published"),
};

const STATUS_DOT_COLORS: Record<PostStatus, string> = {
  published: "bg-emerald-400",
  scheduled: "bg-blue-400",
  draft: "bg-slate-400",
  preview: "bg-slate-400",
  failed: "bg-red-400",
  publishing: "bg-purple-400",
  partially_published: "bg-amber-400",
  pending_approval: "bg-amber-400",
  in_review: "bg-amber-400",
  changes_requested: "bg-red-400",
  client_review: "bg-blue-400",
  approved: "bg-emerald-400",
};

// Labels and colours come from lib/review so the calendar, the list and the
// review panel cannot disagree about what "in_review" looks like.
const STATUS_BADGE_VARIANT = new Proxy({} as Record<string, BadgeVariant>, {
  get: (_target, key: string) => statusMeta(key).variant,
});

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
      className="text-center p-3 rounded-xl transition-colors"
      style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
    >
      <div className="flex justify-center mb-1.5" style={{ color: "var(--page-text-secondary)" }}>{icon}</div>
      <div className="text-lg font-bold tabular-nums" style={{ color: "var(--page-text)" }}>
        {value.toLocaleString()}
      </div>
      <div className="text-[10px] uppercase tracking-wider mt-0.5" style={{ color: "var(--page-text-muted)" }}>
        {label}
      </div>
    </motion.div>
  );
}

// ---------- Main Component ----------
/** Platforms with no per-post metrics API, so a published post there will
 *  never have engagement to show. Kept beside mapPlatform because both answer
 *  "what does this platform actually do". The backend is the authority --
 *  their connectors raise NotSupportedError -- this only phrases it. */
const NO_METRICS_PLATFORMS = new Set<Platform>(["twitter", "linkedin"]);

// Map platform name to Platform type
function mapPlatform(name: string): Platform {
  // Matched on substrings, and `n.includes("x")` caught any platform whose
  // *name contains the letter x*. Harmless with today's five and a trap for
  // the sixth. Exact slugs, with the spellings X actually goes by.
  const n = (name || "").trim().toLowerCase().replace(/\s+/g, "");
  const bySlug: Record<string, Platform> = {
    instagram: "instagram",
    facebook: "facebook",
    linkedin: "linkedin",
    youtube: "youtube",
    twitter: "twitter",
    x: "twitter",
    "x(twitter)": "twitter",
    "x-twitter": "twitter",
    x_twitter: "twitter",
  };
  return bySlug[n] ?? "instagram";
}

export default function CalendarPage() {
  const user = useAuthStore((s) => s.user);
  // Every position and time on this page is the workspace's wall clock, not
  // the viewer's. A post published at 21:29 UTC in a UTC workspace used to
  // show as "2:59 AM" to a viewer in India and land in the wrong day cell.
  const [workspaceTimezone, setWorkspaceTimezone] = useState("UTC");
  const initialView: CalendarView = (
    (localStorage.getItem("calendar_default_view") as CalendarView) ||
    user?.preferences?.appearance?.calendarView ||
    "month"
  );
  const [view, setView] = useState<CalendarView>(initialView);
  const [showQueue, setShowQueue] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);

  useEffect(() => {
    const saved =
      (localStorage.getItem("calendar_default_view") as CalendarView) ||
      user?.preferences?.appearance?.calendarView;
    if (saved && (saved === "week" || saved === "month")) {
      setView(saved);
    }
  }, [user?.preferences?.appearance?.calendarView]);

  const [currentDate, setCurrentDate] = useState(new Date());
  const [platformFilter, setPlatformFilter] = useState<Platform | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusBucket | "all">("all");
  const [selectedPost, setSelectedPost] = useState<CalendarPost | null>(null);
  const [isPublishingNow, setIsPublishingNow] = useState(false);
  // The workspace the panel queries. Read from the store rather than awaited
  // per handler, because the detail modal renders synchronously.
  const workspaceId = getAccountIdSync();

  const handleRetryPublish = async () => {
    if (!selectedPost) return;
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    setIsPublishingNow(true);
    try {
      await api.post(`/accounts/${activeAccountId}/posts/${selectedPost.id}/publish`);
      await handlePostClick(selectedPost);
    } catch (err: any) {
      console.error("Retry publish failed:", err);
    } finally {
      setIsPublishingNow(false);
    }
  };

  /** Open the post in the composer.
   *
   *  `startAt` is which step to land on. "Reschedule" used to call this with no
   *  step and drop the user at step 1 of 4 -- account selection -- with no date
   *  control in sight until they clicked through three screens they had not
   *  asked to revisit. It now opens on the step that actually holds the date.
   */
  const openInComposer = async (startAt?: 1 | 4) => {
    if (!selectedPost) return;
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      const res: any = await api.get(`/accounts/${activeAccountId}/posts/${selectedPost.id}`);
      const fullPost = res.data;
      navigate("/create-post", { state: { post: fullPost, mode: "edit", startAt } });
    } catch (err) {
      console.error("Failed to load post details for edit:", err);
      showError("Failed to load post details for editing");
    }
  };

  const handleEditPost = () => openInComposer(1);
  const handleReschedulePost = () => openInComposer(4);

  const handleDuplicatePost = async () => {
    if (!selectedPost) return;
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      await api.post(`/accounts/${activeAccountId}/posts/${selectedPost.id}/duplicate`);
      showSuccess("Post duplicated as draft successfully!");
      setSelectedPost(null);
      await fetchPosts();
    } catch (err: any) {
      console.error("Duplicate post failed:", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to duplicate post";
      showError(`Failed to duplicate post: ${errMsg}`);
    }
  };

  const handleDeletePost = async () => {
    if (!selectedPost) return;
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    if (!window.confirm("Are you sure you want to delete this post?")) return;
    try {
      await api.delete(`/accounts/${activeAccountId}/posts/${selectedPost.id}`);
      showSuccess("Post deleted successfully!");
      setSelectedPost(null);
      await fetchPosts();
    } catch (err: any) {
      console.error("Delete post failed:", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to delete post";
      showError(`Failed to delete post: ${errMsg}`);
    }
  };

  const handlePostClick = async (post: CalendarPost) => {
    setSelectedPost(post);
    const activeAccountId = await getAccountId();
    if (!activeAccountId) return;
    try {
      const res: any = await api.get(`/accounts/${activeAccountId}/posts/${post.id}`);
      const p = res.data;
      if (p) {
        const updatedPost: CalendarPost = {
          ...post,
          status: mapStatus(p.status),
          // Undefined, not zeroes, when the API reports no performance at
          // all. `performance` is null when a post has no measurements --
          // X and LinkedIn expose no per-post metrics API, so their posts
          // never will. Coalescing that to 0 renders "0 likes", which reads
          // as "nobody engaged" when the truth is "this cannot be measured".
          engagement: p.performance
            ? {
                likes: p.performance.likes ?? 0,
                comments: p.performance.comments ?? 0,
                shares: p.performance.shares ?? 0,
                views: p.performance.views ?? 0,
              }
            : undefined,
          errorMessage: p.error_message || p.posting_results?.[0]?.error || null,
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
    const activeAccountId = await getAccountId();
    if (!activeAccountId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    // Fetched here rather than in its own effect so posts are never mapped
    // against a stale clock: the timezone is known before the first post is
    // positioned, instead of the grid rendering in UTC and jumping.
    let zone = workspaceTimezone;
    try {
      const settings: any = await api.get(`/accounts/${activeAccountId}/settings/`);
      zone = (settings.data ?? settings)?.settings?.timezone || "UTC";
      setWorkspaceTimezone(zone);
    } catch {
      // Leave it as it is; the calendar still renders, on UTC.
    }
    try {
      const res: any = await api.get(`/accounts/${activeAccountId}/posts/?per_page=100`);
      const items = res.data?.items ?? res.data ?? [];
      const mapped: CalendarPost[] = items.map((p: any) => {
        // Determine platform from target_accounts or fallback
        const firstTarget = p.target_accounts?.[0];
        const platformName = firstTarget?.platform_name ?? "Instagram";
        const platform = mapPlatform(platformName);

        // Determine date from scheduled_at, published_at, or created_at
        const rawDate = p.scheduled_at ?? p.published_at ?? p.created_at;
        // A floating Date carrying the workspace's wall clock, so getHours()
        // and the day-cell comparisons below read that clock rather than the
        // browser's. Never sent back to the server.
        const date = rawDate
          ? wallClockDate(rawDate, zone)
          : new Date();

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
          // Undefined, not zeroes, when the API reports no performance at
          // all. `performance` is null when a post has no measurements --
          // X and LinkedIn expose no per-post metrics API, so their posts
          // never will. Coalescing that to 0 renders "0 likes", which reads
          // as "nobody engaged" when the truth is "this cannot be measured".
          engagement: p.performance
            ? {
                likes: p.performance.likes ?? 0,
                comments: p.performance.comments ?? 0,
                shares: p.performance.shares ?? 0,
                views: p.performance.views ?? 0,
              }
            : undefined,
          errorMessage: p.error_message || p.posting_results?.[0]?.error || null,
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
      if (statusFilter !== "all" && bucketOf(p.status) !== statusFilter) return false;
      return true;
    });
  }, [posts, platformFilter, statusFilter]);

  // The visible month as plain YYYY-MM-DD, built from local calendar fields.
  // toISOString() would shift the boundary by the viewer's offset and ask the
  // server about the wrong month for anyone west of UTC.
  const monthRange = useMemo(() => {
    const pad = (n: number) => String(n).padStart(2, "0");
    const y = currentDate.getFullYear();
    const m = currentDate.getMonth();
    const last = new Date(y, m + 1, 0).getDate();
    return {
      from: `${y}-${pad(m + 1)}-01`,
      to: `${y}-${pad(m + 1)}-${pad(last)}`,
    };
  }, [currentDate]);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthName = currentDate.toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  // Stats
  const countIn = (bucket: StatusBucket) =>
    filteredPosts.filter((p) => bucketOf(p.status) === bucket).length;
  const publishedCount = countIn("published");
  const partiallyPublishedCount = countIn("partially_published");
  const scheduledCount = countIn("scheduled");
  const inReviewCount = countIn("in_review");
  const draftCount = countIn("draft");
  const failedCount = countIn("failed");

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
            <div
              className="p-2.5 rounded-xl"
              style={{
                backgroundColor: "var(--accent-soft)",
                border: "1px solid var(--accent-soft-border)",
              }}
            >
              <CalendarDays className="w-6 h-6" style={{ color: "var(--accent)" }} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--page-heading)" }}>
                Content Calendar
              </h1>
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                Plan and schedule your content across platforms
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={() => setShowQueue((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm transition-colors"
              style={{
                backgroundColor: showQueue ? "rgba(109,94,246,0.16)" : "var(--sidebar-hover-bg)",
                color: showQueue ? "var(--page-heading)" : "var(--page-text-secondary)",
                border: "1px solid var(--surface-border)",
              }}
            >
              <ListChecks className="h-4 w-4" />
              Queue
            </button>

            <button
              onClick={() => setShowHeatmap((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm transition-colors"
              style={{
                backgroundColor: showHeatmap ? "rgba(109,94,246,0.16)" : "var(--sidebar-hover-bg)",
                color: showHeatmap ? "var(--page-heading)" : "var(--page-text-secondary)",
                border: "1px solid var(--surface-border)",
              }}
            >
              <Flame className="h-4 w-4" />
              Best times
            </button>

            <button
              onClick={() => setShowSuggestions((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm transition-colors"
              style={{
                backgroundColor: showSuggestions ? "rgba(109,94,246,0.16)" : "var(--sidebar-hover-bg)",
                color: showSuggestions ? "var(--page-heading)" : "var(--page-text-secondary)",
                border: "1px solid var(--surface-border)",
              }}
            >
              <Lightbulb className="h-4 w-4" />
              Suggestions
            </button>

            <button
              onClick={() => setShowImport(true)}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm transition-colors"
              style={{
                backgroundColor: "var(--sidebar-hover-bg)",
                color: "var(--page-text-secondary)",
                border: "1px solid var(--surface-border)",
              }}
            >
              <FileSpreadsheet className="h-4 w-4" />
              Import CSV
            </button>

            {/* View toggle */}
            <div
              className="flex items-center p-1 rounded-xl"
              style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
            >
              {(["week", "month"] as CalendarView[]).map((v) => (
                <button
                  key={v}
                  onClick={() => {
                    setView(v);
                    localStorage.setItem("calendar_default_view", v);
                  }}
                  className={cn(
                    "relative px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 capitalize cursor-pointer",
                    view === v && "font-semibold"
                  )}
                  style={{ color: view === v ? "var(--page-heading)" : "var(--page-text-muted)" }}
                >
                  {view === v && (
                    <motion.div
                      layoutId="viewToggle"
                      className="absolute inset-0 rounded-lg"
                      style={{
                        backgroundColor: "var(--accent-soft)",
                        border: "1px solid var(--accent-soft-border)",
                      }}
                      transition={{ type: "spring", duration: 0.4 }}
                    />
                  )}
                  <span className="relative z-10">{v}</span>
                </button>
              ))}
            </div>

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

        {showImport && workspaceId && (
          <BulkImportDialog
            accountId={workspaceId}
            onClose={() => setShowImport(false)}
            onImported={() => {
              setShowImport(false);
              fetchPosts();
            }}
          />
        )}

        {showHeatmap && workspaceId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="overflow-hidden"
          >
            <BestTimesHeatmap accountId={workspaceId} />
          </motion.div>
        )}

        {showSuggestions && workspaceId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="overflow-hidden"
          >
            {/* The range is the month on display, expressed as plain dates so
                the server reads them on the workspace's clock rather than
                inheriting the viewer's. */}
            <CalendarSuggestions
              accountId={workspaceId}
              from={monthRange.from}
              to={monthRange.to}
              onDrafted={fetchPosts}
            />
          </motion.div>
        )}

        {showQueue && workspaceId && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="overflow-hidden"
          >
            <QueuePanel accountId={workspaceId} />
          </motion.div>
        )}

        {/* Quick stats */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-3"
        >
          {/* "Partly published" and "In review" appear only when they apply:
              they are the two states that had no chip, so posts in them were
              counted as Published and Drafts respectively. A chip that reads 0
              on every normal workspace is noise; one that is missing when it
              matters is a lie. */}
          {[
            {
              label: "Published",
              count: publishedCount,
              color: "emerald",
              dotColor: "bg-emerald-400",
            },
            ...(partiallyPublishedCount
              ? [{
                  label: "Partly published",
                  count: partiallyPublishedCount,
                  color: "amber",
                  dotColor: "bg-amber-400",
                }]
              : []),
            {
              label: "Scheduled",
              count: scheduledCount,
              color: "blue",
              dotColor: "bg-blue-400",
            },
            ...(inReviewCount
              ? [{
                  label: "In review",
                  count: inReviewCount,
                  color: "amber",
                  dotColor: "bg-amber-400",
                }]
              : []),
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
              className="flex items-center gap-3 px-4 py-3 rounded-xl"
              style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}
            >
              <div className={cn("w-2 h-2 rounded-full", stat.dotColor)} />
              <div>
                {isLoading ? (
                  <span className="inline-block w-8 h-5 rounded animate-pulse" style={{ backgroundColor: "var(--sidebar-hover-bg)" }} />
                ) : (
                  <span className="text-lg font-bold tabular-nums" style={{ color: "var(--page-text)" }}>
                    {stat.count}
                  </span>
                )}
                <span className="text-xs ml-2" style={{ color: "var(--page-text-muted)" }}>
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
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 whitespace-nowrap flex-shrink-0 cursor-pointer",
                  platformFilter === p.key &&
                    "bg-[color:var(--accent-soft)] border-[color:var(--accent-soft-border)] text-[color:var(--accent)]"
                )}
                style={
                  platformFilter === p.key
                    ? undefined
                    : { backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)", color: "var(--page-text-muted)" }
                }
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
                  setStatusFilter(s.key)
                }
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 cursor-pointer",
                  statusFilter === s.key &&
                    "bg-[color:var(--accent-soft)] border-[color:var(--accent-soft-border)] text-[color:var(--accent)]"
                )}
                style={
                  statusFilter === s.key
                    ? undefined
                    : { backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)", color: "var(--page-text-muted)" }
                }
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
                className="p-2 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-all duration-200 cursor-pointer"
                style={{ color: "var(--page-text-secondary)" }}
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <button
                onClick={() =>
                  view === "month" ? navigateMonth(1) : navigateWeek(1)
                }
                className="p-2 rounded-lg hover:bg-[var(--sidebar-hover-bg)] transition-all duration-200 cursor-pointer"
                style={{ color: "var(--page-text-secondary)" }}
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            <h2 className="text-lg font-semibold tabular-nums" style={{ color: "var(--page-heading)" }}>
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
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[color:var(--accent-soft)] border border-[color:var(--accent-soft-border)] text-[color:var(--accent)] hover:brightness-95 transition-all duration-200 cursor-pointer"
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
                      className="text-center text-[11px] font-semibold uppercase tracking-wider py-2"
                      style={{ color: "var(--page-text-muted)" }}
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
                          "relative min-h-[120px] rounded-lg p-2 transition-all duration-200 cursor-pointer group",
                          !cell.isCurrentMonth && "opacity-40",
                          isToday && "ring-2 ring-purple-500"
                        )}
                        style={
                          isToday
                            ? { background: "rgba(124,58,237,0.14)", border: "1px solid rgba(124,58,237,0.30)", color: "var(--page-heading)" }
                            : cell.isCurrentMonth
                              ? { backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }
                              : { backgroundColor: "transparent", border: "1px solid transparent" }
                        }
                      >
                        {/* Date number */}
                        <div className="flex items-center justify-between mb-1">
                          <span
                            className={cn(
                              "text-xs font-semibold w-6 h-6 flex items-center justify-center rounded-full tabular-nums",
                              isToday && "bg-[color:var(--accent)] text-white"
                            )}
                            style={
                              isToday
                                ? undefined
                                : { color: cell.isCurrentMonth ? "var(--page-text-secondary)" : "var(--page-text-muted)" }
                            }
                          >
                            {cell.date}
                          </span>
                          {dayPosts.length > 0 && (
                            <span className="text-[9px] font-medium tabular-nums" style={{ color: "var(--page-text-muted)" }}>
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
                            <span className="block text-[9px] pl-1 font-medium tabular-nums" style={{ color: "var(--page-text-muted)" }}>
                              +{dayPosts.length - 3} more
                            </span>
                          )}
                        </div>

                        {/* Hover overlay for empty cells */}
                        {dayPosts.length === 0 && cell.isCurrentMonth && (
                          <div className="absolute inset-0 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            <Plus className="w-5 h-5" style={{ color: "var(--page-text-muted)" }} />
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
                        className="text-center py-2.5 rounded-lg transition-colors"
                        style={
                          isToday_
                            ? { background: "rgba(124,58,237,0.14)", border: "1px solid rgba(124,58,237,0.30)" }
                            : undefined
                        }
                      >
                        <div className="text-[10px] uppercase tracking-wider font-medium" style={{ color: "var(--page-text-muted)" }}>
                          {DAY_NAMES[d.getDay()]}
                        </div>
                        <div
                          className={cn(
                            "text-lg font-bold mt-0.5 tabular-nums",
                            isToday_ && "text-[color:var(--accent)]"
                          )}
                          style={isToday_ ? undefined : { color: "var(--page-heading)" }}
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
                        <div className="text-[10px] text-right pr-2 py-4 font-medium tabular-nums" style={{ color: "var(--page-text-muted)" }}>
                          {formatHour(hour)}
                        </div>
                        {weekDays.map((d, dayIdx) => {
                          const hourPosts = postsForDayDate(d).filter(
                            (p) => p.hour === hour
                          );
                          return (
                            <div
                              key={dayIdx}
                              className="rounded-lg min-h-[52px] p-0.5 hover:bg-[var(--sidebar-hover-bg)] transition-colors relative"
                              style={
                                isSameDay(d, today)
                                  ? { border: "1px solid var(--surface-border)", background: "rgba(124,58,237,0.06)" }
                                  : { border: "1px solid var(--surface-border)" }
                              }
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
                {/* The shared label, not a capitalised raw status. Otherwise
                    a partial publish reads "Partially_published" in the header
                    while the review row beside it says "Partly published". */}
                {statusMeta(selectedPost.status).label}
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
              <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--page-text-secondary)" }}>
                <Clock className="w-3.5 h-3.5" />
                {formatDate(selectedPost.date)}
                {selectedPost.hour !== undefined &&
                  ` at ${formatTime(selectedPost.hour, selectedPost.minute ?? 0)}`}
                {/* Which clock, so a reader in another country knows whose
                    9 AM this is. */}
                <span style={{ color: "var(--page-text-muted)" }}>
                  {` (${workspaceTimezone})`}
                </span>
              </span>
            </div>

            {/* Title */}
            <h3 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
              {selectedPost.title}
            </h3>

            {/* Media Preview */}
            {selectedPost.imageUrl && (
              <div className="w-full h-48 rounded-xl overflow-hidden bg-black/20 flex items-center justify-center" style={{ border: "1px solid var(--surface-border)" }}>
                <img
                  src={selectedPost.imageUrl}
                  alt={selectedPost.title || "Post media preview"}
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Audio/Music Track */}
            {selectedPost.instagramMusicTrack && (
              <div
                className="flex items-center gap-2.5 p-3 rounded-xl"
                style={{
                  backgroundColor: "var(--accent-soft)",
                  border: "1px solid var(--accent-soft-border)",
                  color: "var(--accent)",
                }}
              >
                <Music2 className="w-4 h-4 animate-pulse flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold truncate" style={{ color: "var(--accent)" }}>
                    ♫ {selectedPost.instagramMusicTrack.split(" – ")[0]}
                  </p>
                  {selectedPost.instagramMusicTrack.split(" – ")[1] && (
                    <p className="text-[10px] truncate" style={{ color: "var(--page-text-secondary)" }}>
                      Artist: {selectedPost.instagramMusicTrack.split(" – ")[1]}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Content */}
            <div className="p-4 rounded-xl" style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--page-text)" }}>
                {selectedPost.content}
              </p>
            </div>

            {/* Engagement metrics (published only) */}
            {selectedPost.status === "published" &&
              selectedPost.engagement && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-4 h-4" style={{ color: "var(--accent)" }} />
                    <span className="text-sm font-medium" style={{ color: "var(--page-text)" }}>
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

            {/* An absent measurement is worth a sentence. Without one, a
                published post with no engagement panel just looks unfinished,
                and the obvious "fix" is to draw zeros -- which is the defect
                this replaced. */}
            {selectedPost.status === "published" && !selectedPost.engagement && (
              <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                No engagement data.{" "}
                {NO_METRICS_PLATFORMS.has(selectedPost.platform)
                  ? `${PLATFORM_LABELS[selectedPost.platform]} does not expose per-post metrics, so there is nothing to report.`
                  : "Metrics have not come back from the platform yet."}
              </p>
            )}

            {/* Review: where the post stands, who said what, and the actions
                this role may take. Buttons come from the server's own
                transition matrix, so none of them can 403. */}
            {workspaceId && (
              <ReviewPanel
                postId={selectedPost.id}
                onChanged={() => handlePostClick(selectedPost)}
              />
            )}

            {/* Per-platform publishing status.
                Replaces a single error string with one row per target: its
                attempt count, when the next retry is due, what the platform
                said, and a retry button that reruns only that target. */}
            {workspaceId && (
              <PublishingJobs
                accountId={workspaceId}
                postId={selectedPost.id}
                // No client-side permission gating exists in this app; the API
                // enforces content.publish and returns 403, which the panel
                // surfaces as a toast. Hiding the button here would be a
                // second, driftable copy of the rule.
                canRetry
                onChanged={() => handlePostClick(selectedPost)}
              />
            )}

            {/* Error Message callout */}
            {selectedPost.errorMessage && (
              <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <p className="font-semibold text-red-200">Publishing Details / Warning</p>
                  <p className="leading-normal" style={{ color: "var(--page-text)" }}>{selectedPost.errorMessage}</p>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-3 flex-wrap" style={{ borderTop: "1px solid var(--surface-border)" }}>
              {selectedPost.status === "failed" && (
                <Button
                  variant="primary"
                  icon={<Send className="w-4 h-4" />}
                  size="sm"
                  onClick={handleRetryPublish}
                  disabled={isPublishingNow}
                >
                  {isPublishingNow ? "Publishing..." : "Retry Publishing"}
                </Button>
              )}
              <Button
                variant="secondary"
                icon={<Pencil className="w-4 h-4" />}
                size="sm"
                onClick={handleEditPost}
              >
                Edit
              </Button>
              <Button
                variant="secondary"
                icon={<Copy className="w-4 h-4" />}
                size="sm"
                onClick={handleDuplicatePost}
              >
                Duplicate
              </Button>
              <Button
                variant="secondary"
                icon={<RefreshCw className="w-4 h-4" />}
                size="sm"
                onClick={handleReschedulePost}
              >
                Reschedule
              </Button>
              {(isEditableDraft(selectedPost.status) ||
                selectedPost.status === "scheduled") && (
                <Button
                  variant="danger"
                  icon={<Trash2 className="w-4 h-4" />}
                  size="sm"
                  onClick={handleDeletePost}
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
