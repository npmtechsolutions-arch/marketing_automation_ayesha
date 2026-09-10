import { useEffect, useState } from "react";
import { AlertTriangle, Lightbulb, Loader2, Sparkles } from "lucide-react";

import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { showError, showSuccess } from "@/components/ui/Toast";
import api from "@/lib/api";

/** Gaps in the visible range, and a one-click way to draft into one.
 *
 *  Every gap says how strong the claim behind it is, and they are not styled
 *  alike:
 *
 *    queue    — the workspace itself said it posts at this time. A commitment.
 *    observed — derived from this account's own posts that actually measured.
 *    default  — a platform convention, and nothing to do with this customer.
 *
 *  Flattening those into one "suggestion" badge would make the third sound
 *  like the first, which is the shape of every fabrication this project has
 *  removed.
 *
 *  "Draft a post" produces a **proposal**, reviewed on the monthly-plan screen.
 *  Nothing here schedules into the gap.
 */

interface Gap {
  local_datetime: string;
  run_at: string;
  weekday: number;
  hour: number;
  kind: "queue_slot" | "best_time";
  slot_source: "queue" | "observed" | "default";
  platform: string | null;
  social_account_id: string | null;
  account_name?: string;
  reason: string;
}

interface StalePlatform {
  social_account_id: string;
  account_name: string;
  platform: string;
  days: number;
  reason: string;
}

interface Suggestions {
  window: { from: string; to: string; timezone: string; days: number };
  summary: {
    scheduled_posts: number;
    days_with_nothing: number;
    queue_gaps: number;
    best_time_gaps: number;
  };
  gaps: Gap[];
  stale_platforms: StalePlatform[];
}

const SOURCE_BADGE: Record<
  Gap["slot_source"],
  { label: string; variant: "success" | "info" | "default" }
> = {
  queue: { label: "queue slot", variant: "info" },
  observed: { label: "observed", variant: "success" },
  default: { label: "default time", variant: "default" },
};

export default function CalendarSuggestions({
  accountId,
  from,
  to,
  onDrafted,
}: {
  accountId: string | null;
  from: string;
  to: string;
  onDrafted?: () => void;
}) {
  const [data, setData] = useState<Suggestions | null>(null);
  const [loading, setLoading] = useState(false);
  const [fillingKey, setFillingKey] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res: any = await api.get(
          `/accounts/${accountId}/calendar/suggestions`,
          { params: { from, to } }
        );
        if (!cancelled) setData(res.data ?? res);
      } catch (err: any) {
        if (!cancelled) {
          showError(
            err?.response?.data?.detail || "Could not read calendar suggestions."
          );
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [accountId, from, to]);

  const draftFor = async (gap: Gap) => {
    if (!accountId || !gap.social_account_id) return;
    setFillingKey(gap.local_datetime + gap.social_account_id);
    try {
      const res: any = await api.post(
        `/accounts/${accountId}/calendar/suggest-fill`,
        {
          slots: [
            {
              // The reading the server gave us, sent back unchanged. Routing
              // it through a Date would reinterpret it in the browser's zone.
              local_datetime: gap.local_datetime,
              social_account_id: gap.social_account_id,
            },
          ],
        }
      );
      const plan = res.data ?? res;
      showSuccess(
        `Drafted a proposal for this slot. Review it on the monthly plan — ` +
          `nothing has been scheduled.`
      );
      onDrafted?.();
      return plan;
    } catch (err: any) {
      showError(
        err?.response?.data?.detail || "Could not draft a post for that slot."
      );
    } finally {
      setFillingKey(null);
    }
  };

  if (!accountId) return null;

  if (loading && !data) {
    return (
      <GlassCard>
        <p className="flex items-center gap-2 text-sm"
           style={{ color: "var(--page-text-muted)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          Reading the calendar…
        </p>
      </GlassCard>
    );
  }

  if (!data) return null;

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-1">
        <Lightbulb className="h-4 w-4 text-purple-400" />
        <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
          Suggestions
        </h3>
      </div>
      <p className="text-xs mb-4" style={{ color: "var(--page-text-muted)" }}>
        {data.summary.scheduled_posts} post
        {data.summary.scheduled_posts === 1 ? "" : "s"} scheduled ·{" "}
        {data.summary.days_with_nothing} day
        {data.summary.days_with_nothing === 1 ? "" : "s"} with nothing on them ·
        times on the workspace's clock ({data.window.timezone}).
      </p>

      {data.stale_platforms.length > 0 && (
        <div className="mb-4 space-y-2">
          {data.stale_platforms.map((platform) => (
            <p key={platform.social_account_id}
               className="flex items-start gap-2 text-sm"
               style={{ color: "var(--page-text-secondary)" }}>
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
              {platform.reason}
            </p>
          ))}
        </div>
      )}

      {data.gaps.length === 0 ? (
        // An empty state that says why it is empty.
        <p className="text-sm" style={{ color: "var(--page-text-muted)" }}>
          Nothing to suggest for this range — every queue slot is filled and
          every day has something on it.
        </p>
      ) : (
        <div className="space-y-2">
          {data.gaps.slice(0, 25).map((gap) => {
            const badge = SOURCE_BADGE[gap.slot_source];
            const when = gap.local_datetime;
            const key = when + (gap.social_account_id ?? "");
            const busy = fillingKey === key;
            return (
              <div key={key}
                   className="flex items-start justify-between gap-3 rounded-xl px-3 py-2.5"
                   style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium tabular-nums"
                          style={{ color: "var(--page-heading)" }}>
                      {/* Rendered from the server's local reading, not from a
                          Date — the string already is the workspace's clock. */}
                      {when.slice(0, 10)} {when.slice(11, 16)}
                    </span>
                    <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
                    {gap.account_name && (
                      <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                        {gap.account_name}
                      </span>
                    )}
                  </div>
                  <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                    {gap.reason}
                  </p>
                </div>
                {gap.social_account_id ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={busy}
                    icon={<Sparkles className="h-3.5 w-3.5" />}
                    onClick={() => draftFor(gap)}
                  >
                    Draft a post
                  </Button>
                ) : (
                  // A queue slot is not tied to one account, so there is
                  // nothing to write for until the user picks one.
                  <span className="text-xs shrink-0 self-center"
                        style={{ color: "var(--page-text-muted)" }}>
                    pick an account
                  </span>
                )}
              </div>
            );
          })}
          {data.gaps.length > 25 && (
            <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              {data.gaps.length - 25} more in this range.
            </p>
          )}
        </div>
      )}
    </GlassCard>
  );
}
