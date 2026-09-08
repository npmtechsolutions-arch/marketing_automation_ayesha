/**
 * The analytics API surface, in one place.
 *
 * Every view here asks the backend for the *same* window, using the shared
 * range vocabulary from DateRangeFilter -- the four tabs must never disagree
 * about what "last 30 days" means, and neither must analytics and the
 * dashboard.
 *
 * Two rules from the backend carry all the way to the pixels:
 *
 *  * **Null is not zero.** A platform that does not report reach sends null,
 *    and null renders as an em dash. Showing 0 would be a claim that nobody
 *    saw the post, which is a different and false statement.
 *  * **Cumulative metrics are not summed.** Followers come back as the latest
 *    value in the window, never a sum of daily snapshots.
 */
import api from "@/lib/api";
import { rangeQuery, type DateRangeValue } from "@/components/shared/DateRangeFilter";

export type AnalyticsView = "summary" | "platforms" | "posts" | "audience";

/** A metric plus how it moved against the preceding window. */
export interface MetricDelta {
  value: number | null;
  previous: number | null;
  change: number | null;
  /** Null when either side is missing, or when the previous value was zero. */
  change_percent: number | null;
}

export interface OverviewPayload {
  range: { key: string; start: string; end: string; days: number; timezone: string };
  compared_to: { start: string; end: string };
  metrics: Record<string, MetricDelta>;
  has_data: boolean;
}

export interface PlatformRow {
  platform: string;
  platform_name: string;
  accounts: number;
  followers: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  reach: number | null;
  impressions: number | null;
  video_views: number | null;
  profile_visits: number | null;
  clicks: number | null;
  engagement_rate: number | null;
}

export interface PostRow {
  id: string;
  title: string;
  published_at: string | null;
  engagement: number;
  impressions: number;
  reach: number;
  clicks: number;
  video_views: number;
  engagement_rate: number | null;
}

export interface AudiencePayload {
  series: { date: string; followers: number | null; following: number | null }[];
  current: number | null;
  change: number | null;
  change_percent: number | null;
}

function pathFor(accountId: string, view: AnalyticsView): string {
  return `/accounts/${accountId}/analytics/${view}`;
}

/** Build the query string for a view, extending the shared range params. */
export function analyticsQuery(range: DateRangeValue, extra?: Record<string, string>): string {
  const params = new URLSearchParams(rangeQuery(range));
  for (const [key, value] of Object.entries(extra ?? {})) params.set(key, value);
  return params.toString();
}

export async function fetchAnalytics<T>(
  accountId: string,
  view: AnalyticsView,
  range: DateRangeValue,
  extra?: Record<string, string>
): Promise<T> {
  const res = await api.get(`${pathFor(accountId, view)}?${analyticsQuery(range, extra)}`);
  return res.data as T;
}

/**
 * Download a view as CSV.
 *
 * This goes through the axios instance rather than a plain link because the
 * access token lives in memory, not in a cookie -- a bare `<a href>` to the
 * API would arrive unauthenticated and 401. So the bytes are fetched with the
 * Authorization header attached and handed to the browser as a blob.
 *
 * The filename comes from the server's Content-Disposition when it sends one,
 * so the downloaded file is named for the window it actually covers rather
 * than for whatever the client believed it asked for.
 */
export async function downloadAnalyticsCsv(
  accountId: string,
  view: AnalyticsView,
  range: DateRangeValue,
  extra?: Record<string, string>
): Promise<void> {
  const res = await api.get(
    `${pathFor(accountId, view)}?${analyticsQuery(range, { ...extra, format: "csv" })}`,
    { responseType: "blob" }
  );

  const disposition = String(res.headers?.["content-disposition"] ?? "");
  const match = /filename="?([^"';]+)"?/i.exec(disposition);
  const filename = match ? match[1] : `analytics-${view}.csv`;

  const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoking immediately can race the download in some browsers; a tick is
  // enough and the object is small.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------------------------------------------------------------------------
// Rendering helpers -- the null discipline, made visible
// ---------------------------------------------------------------------------

/** An unreported metric reads as a dash. Never as 0. */
export function metric(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export function signed(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${metric(value)}`;
}

/** Human label for a metric key, used by the overview grid and CSV headers. */
export const METRIC_LABELS: Record<string, string> = {
  followers: "Followers",
  following: "Following",
  posts_count: "Posts",
  likes: "Likes",
  comments: "Comments",
  shares: "Shares",
  saves: "Saves",
  reach: "Reach",
  impressions: "Impressions",
  video_views: "Video views",
  profile_visits: "Profile visits",
  clicks: "Clicks",
  engagement_rate: "Engagement rate",
};
