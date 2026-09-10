/**
 * Competitor tracking on Instagram.
 *
 * The types are deliberately thin, because the API is. Instagram's Business
 * Discovery returns a name, a follower count and a post count for public
 * business accounts — no engagement, no cadence, no audience — so there is
 * nothing here to hang a richer screen off, and a field added speculatively
 * would be an invitation to render a number nobody can measure.
 *
 * Three server-supplied strings do work the UI must not do itself:
 * `staleness_label` (every number here is days old by definition),
 * `trend_pending_label` (one snapshot is a fact, not a line), and
 * `not_tracked` (the add dialog says the absences in the same breath as the
 * offer).
 */
import api from "@/lib/api";

export interface CompetitorSnapshot {
  date: string;
  /** Null where Discovery returned nothing — never zero. */
  followers: number | null;
  media_count: number | null;
}

export interface Competitor {
  id: string;
  platform: string;
  handle: string;
  display_name: string | null;
  profile_url: string;
  is_active: boolean;
  added_at: string | null;
  last_synced_at: string | null;
  next_sync_at: string | null;
  /** "as of 6 days ago" — rendered as sent, beside every number. */
  staleness_label: string;
  last_error: string | null;
  healthy: boolean;
  followers: number | null;
  media_count: number | null;
  snapshot_count: number;
  trend_ready: boolean;
  trend_pending_label: string | null;
  snapshots: CompetitorSnapshot[];
}

export interface CompetitorContext {
  platform: string;
  connected: boolean;
  /** Why the feature is idle, in the server's words. */
  reason: string | null;
  tracked: string[];
  not_tracked: string[];
  not_tracked_reason: string;
  eligibility: string;
  cadence: string;
}

export interface CompetitorStatus extends CompetitorContext {
  used: number;
  limit: number | null;
  sync_interval_days: number;
}

export interface CompetitorList extends CompetitorContext {
  competitors: Competitor[];
}

export interface RefreshResult {
  stored: boolean;
  error: string | null;
  competitor: Competitor;
}

const base = (accountId: string) => `/accounts/${accountId}/competitors`;

export const competitorApi = {
  status: (accountId: string) =>
    api.get<CompetitorStatus>(`${base(accountId)}/status`).then((r) => r.data),

  list: (accountId: string) =>
    api.get<CompetitorList>(`${base(accountId)}/`).then((r) => r.data),

  add: (accountId: string, handle: string) =>
    api.post<Competitor>(`${base(accountId)}/`, { handle }).then((r) => r.data),

  setActive: (accountId: string, id: string, is_active: boolean) =>
    api
      .patch<Competitor>(`${base(accountId)}/${id}`, { is_active })
      .then((r) => r.data),

  remove: (accountId: string, id: string) =>
    api.delete(`${base(accountId)}/${id}`).then(() => undefined),

  /** Refused by the server when the weekly cap has not elapsed. */
  refresh: (accountId: string, id: string) =>
    api.post<RefreshResult>(`${base(accountId)}/${id}/refresh`).then((r) => r.data),
};

/**
 * Follower change between the first and last snapshot we hold.
 *
 * Returns null rather than 0 when it cannot be computed — fewer than two
 * points, or a null at either end. A "0" here would read as "they did not
 * grow", when the truth is "we cannot say".
 */
export function followerChange(
  snapshots: CompetitorSnapshot[]
): { absolute: number; percent: number | null } | null {
  const measured = snapshots.filter((s) => s.followers !== null);
  if (measured.length < 2) return null;

  const first = measured[0].followers as number;
  const last = measured[measured.length - 1].followers as number;
  const absolute = last - first;
  // A percentage needs a denominator. Growth from zero followers has no
  // meaningful rate, and 0% would be a claim rather than an absence.
  const percent = first > 0 ? Math.round(((absolute / first) * 100) * 10) / 10 : null;
  return { absolute, percent };
}

/** The window a chart actually covers, for the caption under it. */
export function coveredRange(snapshots: CompetitorSnapshot[]): string | null {
  if (snapshots.length < 2) return null;
  const from = new Date(snapshots[0].date).toLocaleDateString();
  const to = new Date(snapshots[snapshots.length - 1].date).toLocaleDateString();
  return `${from} – ${to}`;
}
