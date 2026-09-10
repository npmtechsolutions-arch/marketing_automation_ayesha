/**
 * Competitor tracking: follower and post counts for Instagram accounts you name.
 *
 * The design problem here is what the page does *not* show. A competitor
 * screen usually implies engagement, cadence and top content; Business
 * Discovery returns none of those and Meta restricts them on every tier. So
 * the absences are stated where someone decides to use the feature — in the
 * add dialog, before they type a handle — rather than left to be discovered as
 * a sparse card.
 *
 * Two other rules the markup follows:
 *   - every number is rendered beside the server's `staleness_label`, because
 *     the cap is weekly and a figure here is days old by definition;
 *   - a chart is drawn only with two or more snapshots. One point is a fact,
 *     not a line, and a single-point chart invites reading a slope into it.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ExternalLink, Info, Pause, Play, Plus, RefreshCw, Trash2, Users,
} from "lucide-react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import { showError, showSuccess } from "@/components/ui/Toast";
import { getAccountIdSync } from "@/lib/api";
import { detailFrom } from "@/lib/scheduling";
import { chartAxis, chartTooltip, PLATFORM_COLORS } from "@/pages/analytics/chart";
import {
  competitorApi, coveredRange, followerChange,
  type Competitor, type CompetitorStatus,
} from "@/lib/competitors";

const IG = PLATFORM_COLORS.instagram;

function CompetitorCard({
  competitor,
  busy,
  onRefresh,
  onToggle,
  onRemove,
}: {
  competitor: Competitor;
  busy: boolean;
  onRefresh: () => void;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const change = followerChange(competitor.snapshots);
  const range = coveredRange(competitor.snapshots);
  const data = competitor.snapshots.map((s) => ({
    date: new Date(s.date).toLocaleDateString(undefined, {
      month: "short", day: "numeric",
    }),
    followers: s.followers,
  }));

  return (
    <GlassCard className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold" style={{ color: "var(--page-heading)" }}>
              {competitor.display_name ?? `@${competitor.handle}`}
            </span>
            {!competitor.is_active && <Badge variant="warning">Paused</Badge>}
            {!competitor.healthy && <Badge variant="danger">Last check failed</Badge>}
          </div>
          <a
            href={competitor.profile_url}
            target="_blank"
            rel="noreferrer"
            className="mt-0.5 inline-flex items-center gap-1 text-xs hover:underline"
            style={{ color: "var(--page-link)" }}
          >
            @{competitor.handle} <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            aria-label="Check now"
            title="Check now — Instagram allows about one lookup a week"
            onClick={onRefresh}
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={competitor.is_active ? "Pause tracking" : "Resume tracking"}
            title={competitor.is_active ? "Pause tracking" : "Resume tracking"}
            onClick={onToggle}
          >
            {competitor.is_active ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label="Stop tracking this account"
            title="Stop tracking this account"
            onClick={onRemove}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <div>
          <span className="text-2xl font-semibold" style={{ color: "var(--page-heading)" }}>
            {/* An em dash, not a zero: null means Discovery reported nothing. */}
            {competitor.followers === null
              ? "—"
              : competitor.followers.toLocaleString()}
          </span>
          <span className="ml-1.5 text-xs" style={{ color: "var(--page-text-secondary)" }}>
            followers
          </span>
        </div>
        <div className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
          {competitor.media_count === null
            ? "— posts"
            : `${competitor.media_count.toLocaleString()} posts`}
        </div>
        {change && (
          <div className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
            {change.absolute >= 0 ? "+" : ""}
            {change.absolute.toLocaleString()}
            {change.percent !== null && ` (${change.percent}%)`} while tracked
          </div>
        )}
        {/* Never a number without its age. */}
        <div className="text-xs" style={{ color: "var(--page-text-muted)" }}>
          {competitor.staleness_label}
        </div>
      </div>

      {!competitor.healthy && competitor.last_error && (
        <p className="mt-2 text-xs text-red-700 dark:text-red-300">
          {competitor.last_error}
        </p>
      )}

      {competitor.trend_ready ? (
        <div className="mt-3">
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--surface-border)" vertical={false} />
                <XAxis dataKey="date" {...chartAxis} />
                {/* Fitted to the tracked range, not anchored at zero: a
                    follower count that moves 5% on a base of 12,000 is a flat
                    line against a zero axis, which hides the only thing this
                    chart is for. The exact numbers and the percentage are
                    printed above it, and the caption says the axis is scaled,
                    so nothing here reads as bigger than it is. */}
                <YAxis width={56} domain={["auto", "auto"]} {...chartAxis} />
                <Tooltip {...chartTooltip} />
                <Line
                  type="monotone"
                  dataKey="followers"
                  name="Followers"
                  stroke={IG}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  // A week Discovery could not answer is a gap in the line,
                  // not a dive to zero.
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {range && (
            <p className="mt-1 text-center text-[11px]" style={{ color: "var(--page-text-muted)" }}>
              {range} · {competitor.snapshot_count} weekly checks · axis scaled
              to this range
            </p>
          )}
        </div>
      ) : (
        <p
          className="mt-3 rounded-xl border border-dashed border-[color:var(--surface-border)] p-3 text-center text-xs"
          style={{ color: "var(--page-text-secondary)" }}
        >
          {competitor.trend_pending_label}
        </p>
      )}
    </GlassCard>
  );
}

export default function CompetitorsPage() {
  const accountId = getAccountIdSync();
  const [status, setStatus] = useState<CompetitorStatus | null>(null);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [handle, setHandle] = useState("");

  const load = useCallback(async () => {
    if (!accountId) return;
    const [statusData, listData] = await Promise.all([
      competitorApi.status(accountId),
      competitorApi.list(accountId),
    ]);
    setStatus(statusData);
    setCompetitors(listData.competitors);
  }, [accountId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await load();
      } catch (err) {
        showError(detailFrom(err, "Could not load competitors."));
      } finally {
        setLoading(false);
      }
    })();
  }, [load]);

  const atLimit = useMemo(() => {
    if (!status || status.limit === null) return false;
    return status.used >= status.limit;
  }, [status]);

  const add = async () => {
    if (!accountId || !handle.trim()) return;
    setBusy(true);
    try {
      const created = await competitorApi.add(accountId, handle.trim());
      setHandle("");
      setAdding(false);
      await load();
      showSuccess(
        `Tracking @${created.handle}. The next check runs within a week.`
      );
    } catch (err) {
      // The server's message names the actual problem — a handle Instagram
      // cannot see, a private account, a plan limit — so it is shown as sent.
      showError(detailFrom(err, "That account could not be added."));
    } finally {
      setBusy(false);
    }
  };

  const act = async (fn: () => Promise<unknown>, failure: string) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (err) {
      showError(detailFrom(err, failure));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-60 w-full" />
        </div>
      </DashboardLayout>
    );
  }

  // Capability gate. Meta requires the lookup to be made as an Instagram
  // business account, so a workspace without one is told the requirement
  // rather than shown a feature that cannot work.
  if (status && !status.connected) {
    return (
      <DashboardLayout>
        <EmptyState
          icon={<Users className="h-7 w-7" />}
          title="Competitor tracking needs an Instagram business account"
          description={status.reason ?? ""}
          actionLabel="Connect Instagram"
          onAction={() => {
            window.location.href = "/social-accounts";
          }}
        />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold" style={{ color: "var(--page-heading)" }}>
              Competitors
            </h1>
            <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Follower and post counts for Instagram business accounts you name,
              checked about once a week. {status?.eligibility}
            </p>
          </div>
          <Button onClick={() => setAdding(true)} disabled={atLimit}>
            <Plus className="mr-1.5 h-4 w-4" />
            Track an account
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs"
             style={{ color: "var(--page-text-secondary)" }}>
          <span>
            Tracking {status?.used ?? 0}
            {status?.limit === null
              ? " · plan has no limit"
              : ` · plan allows ${status?.limit ?? 0}`}
          </span>
          <span>{status?.cadence}</span>
        </div>
        {atLimit && (
          <p className="text-xs text-amber-600 dark:text-amber-300/90">
            Your plan's competitor allowance is used up. Stop tracking one, or
            upgrade, to add another.
          </p>
        )}

        {competitors.length === 0 ? (
          <EmptyState
            icon={<Users className="h-7 w-7" />}
            title="No competitors tracked yet"
            description={
              "Add an Instagram business account by handle and this records its " +
              "follower and post counts each week. It cannot see engagement, " +
              "posting frequency or audience — Instagram does not share those " +
              "for accounts that have not connected to this app."
            }
            actionLabel="Track an account"
            onAction={() => setAdding(true)}
          />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {competitors.map((competitor) => (
              <CompetitorCard
                key={competitor.id}
                competitor={competitor}
                busy={busy}
                onRefresh={() =>
                  act(async () => {
                    const result = await competitorApi.refresh(
                      accountId!, competitor.id
                    );
                    if (result.error) showError(result.error);
                  }, "That check could not run.")
                }
                onToggle={() =>
                  act(
                    () =>
                      competitorApi.setActive(
                        accountId!, competitor.id, !competitor.is_active
                      ),
                    "Could not change that competitor."
                  )
                }
                onRemove={() =>
                  act(
                    () => competitorApi.remove(accountId!, competitor.id),
                    "Could not stop tracking that account."
                  )
                }
              />
            ))}
          </div>
        )}
      </div>

      <Modal
        isOpen={adding}
        onClose={() => setAdding(false)}
        title="Track an Instagram account"
      >
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs" style={{ color: "var(--page-text-secondary)" }}>
              Instagram handle
            </label>
            <input
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") add();
              }}
              placeholder="@nike"
              className="w-full rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)]"
              style={{
                border: "1px solid var(--surface-border)",
                backgroundColor: "var(--input-bg)",
                color: "var(--page-text)",
              }}
            />
            <p className="mt-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
              {status?.eligibility}
            </p>
          </div>

          {/* The absences, stated before anyone commits to the feature rather
              than discovered later as a thin card. */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[color:var(--surface-border)] p-3">
              <p className="mb-1.5 text-xs font-semibold" style={{ color: "var(--page-heading)" }}>
                What gets tracked
              </p>
              <ul className="space-y-1 text-xs" style={{ color: "var(--page-text-secondary)" }}>
                {(status?.tracked ?? []).map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-[color:var(--surface-border)] p-3">
              <p className="mb-1.5 text-xs font-semibold" style={{ color: "var(--page-heading)" }}>
                What does not
              </p>
              <ul className="space-y-1 text-xs" style={{ color: "var(--page-text-secondary)" }}>
                {(status?.not_tracked ?? []).map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          </div>

          <p className="flex items-start gap-2 text-xs" style={{ color: "var(--page-text-muted)" }}>
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {status?.not_tracked_reason}
          </p>

          <p className="flex items-start gap-2 text-xs" style={{ color: "var(--page-text-muted)" }}>
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Adding an account checks the handle with Instagram straight away, so
            a handle that cannot be seen is refused now rather than tracked as
            an empty row.
          </p>

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button onClick={add} disabled={busy || !handle.trim()}>
              {busy ? "Checking…" : "Track account"}
            </Button>
          </div>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
