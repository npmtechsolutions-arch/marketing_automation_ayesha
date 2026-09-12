import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  HandHelping,
  Loader2,
  RefreshCw,
  RotateCw,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import PlatformIcon from "@/components/shared/PlatformIcon";
import { showError, showSuccess } from "@/components/ui/Toast";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

/** Mirrors app/schemas/publishing_job.py */
interface PublishingLogEntry {
  id: string;
  level: "info" | "warning" | "error";
  message: string;
  platform_response: Record<string, unknown> | null;
  created_at: string;
}

interface PublishingJob {
  id: string;
  post_id: string;
  social_account_id: string;
  platform_slug: string | null;
  account_name: string | null;
  status: "queued" | "claimed" | "running" | "succeeded" | "failed" | "cancelled";
  run_at: string;
  attempts: number;
  max_attempts: number;
  attempts_remaining: number;
  last_error: string | null;
  manual_required: boolean;
  external_post_id: string | null;
  post_url: string | null;
  logs: PublishingLogEntry[];
}

interface JobList {
  post_id: string;
  post_status: string;
  jobs: PublishingJob[];
}

const STATUS_META: Record<
  PublishingJob["status"],
  {
    label: string;
    variant: "success" | "danger" | "warning" | "info" | "default";
    icon: typeof Clock;
  }
> = {
  queued: { label: "Queued", variant: "info", icon: Clock },
  claimed: { label: "Starting", variant: "info", icon: Loader2 },
  running: { label: "Publishing", variant: "info", icon: Loader2 },
  succeeded: { label: "Published", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "danger", icon: XCircle },
  cancelled: { label: "Cancelled", variant: "default", icon: XCircle },
};

// Statuses that change on their own, so the panel polls while any job is in one
// and stops once everything has settled.
const IN_FLIGHT = new Set(["queued", "claimed", "running"]);

const ICON_PLATFORMS = [
  "facebook", "instagram", "linkedin", "tiktok", "twitter", "youtube",
] as const;
type IconPlatform = (typeof ICON_PLATFORMS)[number];

/** The slug comes from a per-workspace platform row, so it is not guaranteed
 *  to be one the icon set covers. */
function isKnownPlatform(slug: string | null): slug is IconPlatform {
  return !!slug && (ICON_PLATFORMS as readonly string[]).includes(slug);
}

const errorDetail = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
};

function relativeTime(iso: string): string {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  if (seconds > 60) return `in ${Math.round(seconds / 60)}m`;
  if (seconds > 0) return `in ${seconds}s`;
  return "shortly";
}

export function PublishingJobs({
  accountId,
  postId,
  canRetry,
  onChanged,
}: {
  accountId: string;
  postId: string;
  /** Retrying needs content.publish; viewing the status does not. */
  canRetry: boolean;
  onChanged?: () => void;
}) {
  const [data, setData] = useState<JobList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res: any = await api.get(`/accounts/${accountId}/posts/${postId}/jobs`);
      setData(res.data ?? res);
      setError(null);
    } catch (err: any) {
      setError(errorDetail(err, "Could not load publishing status."));
    }
    setLoading(false);
  }, [accountId, postId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!data?.jobs.some((j) => IN_FLIGHT.has(j.status))) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [data, load]);

  const retry = async (jobId: string) => {
    setRetrying(jobId);
    try {
      await api.post(`/accounts/${accountId}/posts/${postId}/jobs/${jobId}/retry`);
      showSuccess("Queued for another attempt.");
      await load();
      onChanged?.();
    } catch (err: any) {
      showError(errorDetail(err, "Could not retry this job."));
    }
    setRetrying(null);
  };

  if (loading) {
    return (
      <div
        className="flex items-center gap-2 text-xs"
        style={{ color: "var(--page-text-muted)" }}
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Loading publishing status…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex items-center gap-2 text-xs text-amber-400">
        <AlertCircle className="w-3.5 h-3.5" />
        {error}
      </div>
    );
  }
  if (!data || data.jobs.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4
          className="text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--page-text-secondary)" }}
        >
          Publishing
        </h4>
        <button
          onClick={load}
          className="text-xs flex items-center gap-1 hover:opacity-80"
          style={{ color: "var(--page-text-muted)" }}
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>

      {data.jobs.map((job) => {
        // A job that failed because the platform has no API is not something a
        // retry can fix -- it needs publishing by hand.
        const meta = job.manual_required
          ? { label: "Publish by hand", variant: "warning" as const, icon: HandHelping }
          : STATUS_META[job.status];
        const Icon = meta.icon;
        const spinning = job.status === "running" || job.status === "claimed";
        const isOpen = expanded === job.id;

        return (
          <div
            key={job.id}
            className="rounded-xl p-3 space-y-2"
            style={{
              backgroundColor: "var(--sidebar-hover-bg)",
              border: "1px solid var(--surface-border)",
            }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {isKnownPlatform(job.platform_slug) && (
                  <PlatformIcon platform={job.platform_slug} size="sm" />
                )}
                <span className="text-sm truncate" style={{ color: "var(--page-text)" }}>
                  {job.account_name || job.platform_slug || "Account"}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {job.attempts > 0 && (
                  <span
                    className="text-[10px] tabular-nums"
                    style={{ color: "var(--page-text-muted)" }}
                  >
                    attempt {job.attempts}/{job.max_attempts}
                  </span>
                )}
                <Badge variant={meta.variant}>
                  <span className="flex items-center gap-1">
                    <Icon className={cn("w-3 h-3", spinning && "animate-spin")} />
                    {meta.label}
                  </span>
                </Badge>
              </div>
            </div>

            {job.status === "queued" && job.attempts > 0 && (
              <p className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>
                Retrying {relativeTime(job.run_at)}
              </p>
            )}

            {job.last_error && (
              <p className="text-[11px] text-red-400 break-words">{job.last_error}</p>
            )}

            {job.post_url && job.status === "succeeded" && (
              <a
                href={job.post_url}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-purple-400 hover:underline break-all"
              >
                {job.post_url}
              </a>
            )}

            <div className="flex items-center gap-3 pt-1">
              {canRetry && (job.status === "failed" || job.status === "cancelled") && (
                <Button
                  variant="secondary"
                  loading={retrying === job.id}
                  icon={<RotateCw className="w-3 h-3" />}
                  onClick={() => retry(job.id)}
                >
                  Retry
                </Button>
              )}
              {job.logs.length > 0 && (
                <button
                  onClick={() => setExpanded(isOpen ? null : job.id)}
                  className="text-[11px] hover:opacity-80"
                  style={{ color: "var(--page-text-muted)" }}
                >
                  {isOpen ? "Hide" : "Show"} history ({job.logs.length})
                </button>
              )}
            </div>

            {isOpen && (
              <ul
                className="space-y-1.5 pt-1"
                style={{ borderTop: "1px solid var(--surface-border)" }}
              >
                {job.logs.map((entry) => (
                  <li key={entry.id} className="text-[11px] pt-1.5">
                    <span
                      className={cn(
                        "font-medium",
                        entry.level === "error" && "text-red-400",
                        entry.level === "warning" && "text-amber-400"
                      )}
                      style={
                        entry.level === "info"
                          ? { color: "var(--page-text-secondary)" }
                          : undefined
                      }
                    >
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                    <span
                      className="ml-2 break-words"
                      style={{ color: "var(--page-text)" }}
                    >
                      {entry.message}
                    </span>
                    {entry.platform_response && (
                      <pre
                        className="mt-1 p-2 rounded-lg overflow-x-auto text-[10px]"
                        style={{
                          backgroundColor: "var(--input-bg)",
                          color: "var(--page-text-muted)",
                        }}
                      >
                        {JSON.stringify(entry.platform_response, null, 2)}
                      </pre>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default PublishingJobs;
