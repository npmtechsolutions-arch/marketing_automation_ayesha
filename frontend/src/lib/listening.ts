/**
 * Social listening on X.
 *
 * Two fields carry more weight than the rest and are typed as required for
 * that reason.
 *
 * `window_label` is the server's own phrase for how far back the search can
 * reach ("the last 7 days"). The page renders it rather than composing its
 * own, because "no mentions" is a claim about the world and "no mentions in
 * the last 7 days" is a claim about what was looked at — and only the second
 * one is true. If X's tier ever changes, the phrase changes in one place.
 *
 * `last_error` / `healthy` are what separate a quiet week from a broken
 * search. Both return nothing; only one of them is fine.
 */
import api from "@/lib/api";

export interface ListeningWindow {
  platform: string;
  window_days: number | null;
  window_label: string;
  connected: boolean;
  /** Why the feature is idle, in words the page shows as-is. */
  reason: string | null;
  cost_note: string;
}

export interface ListeningQuery {
  id: string;
  platform: string;
  query_text: string;
  is_active: boolean;
  created_at: string | null;
  last_polled_at: string | null;
  last_success_at: string | null;
  next_poll_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  healthy: boolean;
  requests_made: number;
  posts_read: number;
  estimated_cost_usd: number;
}

export interface Mention {
  id: string;
  listening_query_id: string;
  external_id: string;
  author_handle: string | null;
  author_name: string | null;
  text: string;
  posted_at: string | null;
  url: string | null;
  matched_at: string | null;
}

export interface ListeningStatus extends ListeningWindow {
  interval_hours: number;
  interval_options: number[];
  max_results_per_poll: number;
  read_cost_usd: number;
  queries_used: number;
  queries_limit: number | null;
}

export interface QueryList extends ListeningWindow {
  interval_hours: number;
  queries: ListeningQuery[];
}

export interface MentionList extends ListeningWindow {
  total: number;
  limit: number;
  offset: number;
  /** The server's own empty-state sentence, window included. */
  empty_label: string | null;
  mentions: Mention[];
}

export interface PollResult extends ListeningWindow {
  new_mentions: number;
  posts_read: number;
  estimated_cost_usd: number;
  error: string | null;
  query: ListeningQuery;
}

export interface MentionFilters {
  query_id?: string;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

const base = (accountId: string) => `/accounts/${accountId}/listening`;

export const listeningApi = {
  status: (accountId: string) =>
    api.get<ListeningStatus>(`${base(accountId)}/status`).then((r) => r.data),

  queries: (accountId: string) =>
    api.get<QueryList>(`${base(accountId)}/queries`).then((r) => r.data),

  create: (accountId: string, query_text: string) =>
    api
      .post<ListeningQuery>(`${base(accountId)}/queries`, { query_text })
      .then((r) => r.data),

  update: (
    accountId: string,
    queryId: string,
    patch: { is_active?: boolean; query_text?: string }
  ) =>
    api
      .patch<ListeningQuery>(`${base(accountId)}/queries/${queryId}`, patch)
      .then((r) => r.data),

  remove: (accountId: string, queryId: string) =>
    api.delete(`${base(accountId)}/queries/${queryId}`).then(() => undefined),

  /** Explicit, because it spends money. */
  pollNow: (accountId: string, queryId: string) =>
    api
      .post<PollResult>(`${base(accountId)}/queries/${queryId}/poll`)
      .then((r) => r.data),

  mentions: (accountId: string, filters: MentionFilters = {}) => {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return api
      .get<MentionList>(`${base(accountId)}/mentions?${query}`)
      .then((r) => r.data);
  },
};

/**
 * What a poll of `n` queries costs per day at a given interval.
 *
 * Shown in the UI rather than kept in a doc: the interval control is where
 * someone decides to spend six times as much, so the arithmetic belongs next
 * to it. Deliberately an *upper bound* — a poll that finds three posts is
 * billed for three, not for the ceiling — and the label says so.
 */
export function dailyCeilingUsd(
  queries: number,
  intervalHours: number,
  maxResults: number,
  readCost: number
): number {
  if (!queries || !intervalHours) return 0;
  const pollsPerDay = 24 / intervalHours;
  return Math.round(queries * pollsPerDay * maxResults * readCost * 100) / 100;
}

/** Whether a query has never successfully run. */
export function neverRan(query: ListeningQuery): boolean {
  return query.last_success_at === null;
}
