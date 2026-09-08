/**
 * Suggested posting times.
 *
 * The `source` field and each cell's `observed` flag are not decoration — they
 * are the contract. Below the sample threshold these are the platform's usual
 * posting times, not this account's data, and rendering them identically is
 * exactly the fabrication this feature replaced.
 */
import api from "@/lib/api";

export interface HeatCell {
  weekday: number;
  hour: number;
  posts: number;
  /** Null for a slot never tried — not zero, which would claim nobody engaged. */
  score: number | null;
  observed: boolean;
}

export interface Suggestion {
  weekday: number;
  hour: number;
  label: string;
  score: number | null;
  posts: number;
  observed: boolean;
}

export interface BestTimes {
  scope: {
    social_account_id: string | null;
    platform: string | null;
    account_name: string | null;
    timezone: string;
    window_days: number;
  };
  sample: { posts: number; threshold: number; sufficient: boolean };
  source: "observed" | "default";
  explanation: string;
  heatmap: HeatCell[];
  suggestions: Suggestion[];
}

export interface SlotSuggestion extends Suggestion {
  run_at: string;
  /** "2026-09-14T10:00", already on the workspace's clock. */
  local: string;
}

export const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const base = (accountId: string) => `/accounts/${accountId}/analytics/best-times`;

export function fetchBestTimes(
  accountId: string,
  socialAccountId?: string | null
): Promise<BestTimes> {
  const query = socialAccountId ? `?social_account_id=${socialAccountId}` : "";
  return api.get<BestTimes>(`${base(accountId)}${query}`).then((r) => r.data);
}

export function fetchSuggestedSlots(
  accountId: string,
  socialAccountId?: string | null
): Promise<{ source: string; timezone: string; explanation: string; slots: SlotSuggestion[] }> {
  const query = socialAccountId ? `?social_account_id=${socialAccountId}` : "";
  return api.get(`${base(accountId)}/next${query}`).then((r) => r.data);
}

/**
 * A cell's colour intensity, 0–1, scaled against the best observed cell.
 *
 * Unobserved cells return null rather than 0 so the caller renders them as
 * "no data" rather than as "bad" — a dark square and an empty one must not
 * look the same.
 */
export function intensity(cell: HeatCell, best: number): number | null {
  if (!cell.observed || cell.score === null || best <= 0) return null;
  return Math.max(0.08, Math.min(1, cell.score / best));
}
