/** Typed access to the superadmin endpoints. */
import api from "@/lib/api";

export interface PlanRevenueRow {
  plan: string;
  organizations: number;
  active: number;
  mrr: number;
}

export interface RevenueSummary {
  mrr: number;
  arr: number;
  at_risk_mrr: number;
  paying_organizations: number;
  by_status: Record<string, number>;
  by_plan: PlanRevenueRow[];
  /** Active organizations on a plan with no price. MRR excludes them. */
  unpriced_active_organizations: number;
  unpriced_tiers: string[];
  churn: {
    days: number;
    churned_organizations: number;
    lost_mrr: number;
    /** Null when nobody could have churned — not 0%. */
    churn_rate: number | null;
  };
  trials: {
    days: number;
    converted: number;
    trials_ended: number;
    trialing_now: number;
    conversion_rate: number | null;
  };
  /** When the subscription event log starts. Null means no history yet. */
  tracking_since: string | null;
}

export interface RevenueTrend {
  days: number;
  series: { date: string; mrr: number }[];
  tracking_since: string | null;
  has_history: boolean;
}

export interface FailedConnection {
  id: string;
  account_name: string;
  platform: string;
  detail: string | null;
  checked_at: string | null;
  workspace_id: string;
  workspace: string;
  organization_id: string | null;
  organization: string | null;
  plan: string | null;
}

export interface ConnectionHealth {
  counts: Record<string, number>;
  total: number;
  failed: FailedConnection[];
}

export interface ApiErrorRow {
  id: string;
  path: string;
  method: string;
  status_code: number;
  exception_class: string;
  message: string | null;
  user_id: string | null;
  organization_id: string | null;
  created_at: string;
}

export interface ApiErrorDetail extends ApiErrorRow {
  traceback: string | null;
}

export interface ApiErrorPage {
  items: ApiErrorRow[];
  total: number;
  page: number;
  page_size: number;
  retention_days: number;
}

export interface ApiErrorSummary {
  days: number;
  total: number;
  by_exception: { exception_class: string; count: number; last_seen: string | null }[];
  by_path: { path: string; count: number }[];
}

export const adminApi = {
  revenue: (days = 30) =>
    api.get<RevenueSummary>(`/admin/revenue?days=${days}`).then((r) => r.data),
  revenueTrend: (days = 90) =>
    api.get<RevenueTrend>(`/admin/revenue/trend?days=${days}`).then((r) => r.data),
  connectionHealth: () =>
    api.get<ConnectionHealth>("/admin/connection-health").then((r) => r.data),
  errors: (params: {
    page?: number;
    exception_class?: string;
    path?: string;
  } = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.exception_class) query.set("exception_class", params.exception_class);
    if (params.path) query.set("path", params.path);
    return api.get<ApiErrorPage>(`/admin/errors?${query}`).then((r) => r.data);
  },
  errorSummary: (days = 7) =>
    api.get<ApiErrorSummary>(`/admin/errors/summary?days=${days}`).then((r) => r.data),
  error: (id: string) =>
    api.get<ApiErrorDetail>(`/admin/errors/${id}`).then((r) => r.data),
  stats: () => api.get("/admin/stats").then((r) => r.data),
};

/** Money, rendered. Null is a dash, never $0 — the two mean different things. */
export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  });
}

/** A rate that has no denominator is unknown, not zero. */
export function rate(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}
