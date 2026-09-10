/**
 * Social listening: saved searches on X, and what they found.
 *
 * Almost every sentence about scope on this page comes from the server. The
 * window ("the last 7 days"), the empty-state line, and the reason the feature
 * is idle are all rendered as sent, so a change in what X's tier allows moves
 * this page without anyone editing it — and so no component can quietly render
 * "no mentions" where the truth is "no mentions in the seven days we can see".
 *
 * The other thing this page refuses to do is show a broken search as a quiet
 * one. A query whose last poll failed carries its reason in the list, in red,
 * above the stream: an empty stream is a normal answer, so the failure has to
 * be visible somewhere that is not the stream.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ExternalLink, Pause, Play, Plus, RefreshCw,
  Search, Trash2,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { showError, showSuccess } from "@/components/ui/Toast";
import api, { getAccountIdSync } from "@/lib/api";
import { detailFrom } from "@/lib/scheduling";
import {
  dailyCeilingUsd, listeningApi,
  type ListeningQuery, type ListeningStatus, type Mention,
} from "@/lib/listening";

function whenLabel(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(iso).toLocaleDateString();
}

export default function ListeningPage() {
  const accountId = getAccountIdSync();
  const [status, setStatus] = useState<ListeningStatus | null>(null);
  const [queries, setQueries] = useState<ListeningQuery[]>([]);
  const [mentions, setMentions] = useState<Mention[]>([]);
  const [emptyLabel, setEmptyLabel] = useState<string | null>(null);
  const [windowLabel, setWindowLabel] = useState("");
  const [selected, setSelected] = useState<string>("");
  const [since, setSince] = useState<string>("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadQueries = useCallback(async () => {
    if (!accountId) return;
    const [statusData, queryData] = await Promise.all([
      listeningApi.status(accountId),
      listeningApi.queries(accountId),
    ]);
    setStatus(statusData);
    setQueries(queryData.queries);
    setWindowLabel(queryData.window_label);
  }, [accountId]);

  const loadMentions = useCallback(async () => {
    if (!accountId) return;
    const data = await listeningApi.mentions(accountId, {
      query_id: selected || undefined,
      since: since ? new Date(since).toISOString() : undefined,
    });
    setMentions(data.mentions);
    setEmptyLabel(data.empty_label);
    setWindowLabel(data.window_label);
  }, [accountId, selected, since]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await loadQueries();
      } catch (err) {
        showError(detailFrom(err, "Could not load listening."));
      } finally {
        setLoading(false);
      }
    })();
  }, [loadQueries]);

  useEffect(() => {
    loadMentions().catch((err) =>
      showError(detailFrom(err, "Could not load mentions."))
    );
  }, [loadMentions]);

  const atLimit = useMemo(() => {
    if (!status || status.queries_limit === null) return false;
    return status.queries_used >= status.queries_limit;
  }, [status]);

  const ceiling = useMemo(() => {
    if (!status) return 0;
    return dailyCeilingUsd(
      queries.filter((q) => q.is_active).length,
      status.interval_hours,
      status.max_results_per_poll,
      status.read_cost_usd
    );
  }, [status, queries]);

  const broken = useMemo(() => queries.filter((q) => !q.healthy), [queries]);

  const create = async () => {
    if (!accountId || !draft.trim()) return;
    setBusy(true);
    try {
      await listeningApi.create(accountId, draft.trim());
      setDraft("");
      await loadQueries();
      showSuccess("Watching that search. The first poll runs on the next sweep.");
    } catch (err) {
      showError(detailFrom(err, "Could not save that search."));
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (query: ListeningQuery) => {
    if (!accountId) return;
    try {
      await listeningApi.update(accountId, query.id, {
        is_active: !query.is_active,
      });
      await loadQueries();
    } catch (err) {
      showError(detailFrom(err, "Could not change that search."));
    }
  };

  const remove = async (query: ListeningQuery) => {
    if (!accountId) return;
    try {
      await listeningApi.remove(accountId, query.id);
      if (selected === query.id) setSelected("");
      await loadQueries();
      await loadMentions();
    } catch (err) {
      showError(detailFrom(err, "Could not delete that search."));
    }
  };

  const pollNow = async (query: ListeningQuery) => {
    if (!accountId) return;
    setBusy(true);
    try {
      const result = await listeningApi.pollNow(accountId, query.id);
      await loadQueries();
      await loadMentions();
      if (result.error) {
        showError(result.error);
      } else {
        showSuccess(
          `${result.new_mentions} new — read ${result.posts_read} post(s), ` +
            `about $${result.estimated_cost_usd.toFixed(3)}.`
        );
      }
    } catch (err) {
      showError(detailFrom(err, "The search could not run."));
    } finally {
      setBusy(false);
    }
  };

  const setInterval_ = async (hours: number) => {
    if (!accountId) return;
    try {
      await api.put(`/accounts/${accountId}/settings/`, {
        settings: { listening_interval_hours: hours },
      });
      await loadQueries();
      showSuccess(`Polling every ${hours}h.`);
    } catch (err) {
      showError(detailFrom(err, "Could not change the polling interval."));
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </DashboardLayout>
    );
  }

  // Capability gate. A workspace with no X connection is told why the feature
  // is idle rather than shown an empty page it cannot act on.
  if (status && !status.connected) {
    return (
      <DashboardLayout>
        <EmptyState
          icon={<Search className="h-7 w-7" />}
          title="Listening needs an X connection"
          description={
            status.reason ??
            "Listening runs on X. Connect an X account to watch a search."
          }
          actionLabel="Connect an account"
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
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--page-heading)" }}
          >
            Listening
          </h1>
          {/* The scope, stated at the top rather than implied by an empty list. */}
          <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
            Saved searches on X, covering {windowLabel || "the platform's search window"}.
            X's API cannot look further back than that, so anything older is not
            missing — it is out of reach.
          </p>
        </div>

        {broken.length > 0 && (
          <GlassCard className="border-red-500/40 bg-red-500/5 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <div className="text-sm">
                <p className="font-semibold text-red-700 dark:text-red-300">
                  {broken.length === 1
                    ? "A search is not running."
                    : `${broken.length} searches are not running.`}
                </p>
                <ul className="mt-1 space-y-1 text-xs text-red-700/90 dark:text-red-200/90">
                  {broken.map((query) => (
                    <li key={query.id}>
                      <span className="font-mono">{query.query_text}</span> —{" "}
                      {query.last_error}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs font-medium text-red-700/80 dark:text-red-200/70">
                  Until this is fixed the stream below is not evidence of
                  quiet — the search has not run.
                </p>
              </div>
            </div>
          </GlassCard>
        )}

        <GlassCard className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") create();
              }}
              placeholder="A search to watch, e.g. marketengine OR @marketengine"
              disabled={atLimit}
              className="min-w-[16rem] flex-1 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[rgba(124,58,237,0.20)]"
              style={{
                border: "1px solid var(--surface-border)",
                backgroundColor: "var(--input-bg)",
                color: "var(--page-text)",
              }}
            />
            <Button onClick={create} disabled={busy || atLimit || !draft.trim()}>
              <Plus className="mr-1.5 h-4 w-4" />
              Watch
            </Button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs"
               style={{ color: "var(--page-text-secondary)" }}>
            <span>
              Watching {status?.queries_used ?? 0}
              {status?.queries_limit === null
                ? " · plan has no limit"
                : ` · plan allows ${status?.queries_limit ?? 0}`}
            </span>
            <span className="flex items-center gap-1.5">
              Polling every
              {(status?.interval_options ?? []).map((hours) => (
                <button
                  key={hours}
                  onClick={() => setInterval_(hours)}
                  className={
                    hours === status?.interval_hours
                      ? "rounded-md bg-purple-500/20 px-1.5 py-0.5 font-medium text-purple-700 dark:text-purple-200"
                      : "rounded-md px-1.5 py-0.5 hover:bg-purple-500/10"
                  }
                >
                  {hours}h
                </button>
              ))}
            </span>
            {/* The arithmetic sits next to the control that changes it: this is
                the place someone decides to spend six times as much. */}
            <span>
              At most about ${ceiling.toFixed(2)}/day in X API reads at this
              interval — usually far less, since a poll is billed for the posts
              it actually finds.
            </span>
          </div>
          {atLimit && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-300/90">
              Your plan's listening allowance is used up. Delete a search or
              upgrade to watch another.
            </p>
          )}
        </GlassCard>

        <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
          <GlassCard className="p-3">
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-xs uppercase tracking-wide"
                    style={{ color: "var(--page-text-secondary)" }}>
                Searches
              </span>
              <button
                onClick={() => setSelected("")}
                className={
                  selected === ""
                    ? "text-xs text-purple-300"
                    : "text-xs text-slate-400 hover:text-slate-200"
                }
              >
                All
              </button>
            </div>

            {queries.length === 0 && (
              <p className="px-2 py-6 text-center text-xs"
                 style={{ color: "var(--page-text-secondary)" }}>
                No searches yet. Watch one above.
              </p>
            )}

            <ul className="space-y-1.5">
              {queries.map((query) => (
                <li
                  key={query.id}
                  className={
                    "rounded-xl border p-2.5 " +
                    (selected === query.id
                      ? "border-purple-500/40 bg-purple-500/10"
                      : "border-[color:var(--surface-border)] hover:bg-purple-500/5")
                  }
                >
                  <button
                    onClick={() => setSelected(query.id)}
                    className="block w-full text-left"
                  >
                    <span className="font-mono text-sm"
                          style={{ color: "var(--page-heading)" }}>
                      {query.query_text}
                    </span>
                  </button>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]"
                       style={{ color: "var(--page-text-secondary)" }}>
                    {!query.is_active && <Badge variant="warning">Paused</Badge>}
                    {!query.healthy && <Badge variant="danger">Not running</Badge>}
                    <span>polled {whenLabel(query.last_polled_at)}</span>
                    <span>·</span>
                    <span>
                      {query.posts_read} read (~$
                      {query.estimated_cost_usd.toFixed(2)})
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={query.is_active ? "Pause this search" : "Resume this search"}
                      title={query.is_active ? "Pause this search" : "Resume this search"}
                      onClick={() => toggle(query)}
                    >
                      {query.is_active ? (
                        <Pause className="h-3.5 w-3.5" />
                      ) : (
                        <Play className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => pollNow(query)}
                      aria-label="Run this search now"
                      title="Run this search now — this spends X API credit"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label="Delete this search"
                      title="Delete this search"
                      onClick={() => remove(query)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </GlassCard>

          <GlassCard className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <span className="text-xs uppercase tracking-wide"
                    style={{ color: "var(--page-text-secondary)" }}>
                Mentions
              </span>
              <label className="flex items-center gap-1.5 text-xs"
                     style={{ color: "var(--page-text-secondary)" }}>
                Posted since
                <input
                  type="date"
                  value={since}
                  onChange={(e) => setSince(e.target.value)}
                  className="rounded-lg px-2 py-1 text-xs"
                  style={{
                    border: "1px solid var(--surface-border)",
                    backgroundColor: "var(--input-bg)",
                    color: "var(--page-text)",
                  }}
                />
              </label>
              {since && (
                <button
                  onClick={() => setSince("")}
                  className="text-xs hover:underline" style={{ color: "var(--page-text-muted)" }}
                >
                  Clear
                </button>
              )}
            </div>

            {mentions.length === 0 ? (
              <p className="py-10 text-center text-sm"
                 style={{ color: "var(--page-text-secondary)" }}>
                {/* The server's sentence, window included, rendered as sent. */}
                {emptyLabel ?? `No mentions in ${windowLabel}.`}
              </p>
            ) : (
              <ul className="space-y-2">
                {mentions.map((mention) => (
                  <li
                    key={mention.id}
                    className="rounded-xl border border-[color:var(--surface-border)] p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium"
                            style={{ color: "var(--page-heading)" }}>
                        {mention.author_name ?? "Someone"}
                        {mention.author_handle && (
                          <span className="ml-1.5 text-xs font-normal" style={{ color: "var(--page-text-muted)" }}>
                            @{mention.author_handle}
                          </span>
                        )}
                      </span>
                      <span className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>
                        {mention.posted_at
                          ? new Date(mention.posted_at).toLocaleString()
                          : "date unknown"}
                      </span>
                    </div>
                    <p className="mt-1.5 whitespace-pre-wrap text-sm"
                       style={{ color: "var(--page-text-secondary)" }}>
                      {mention.text}
                    </p>
                    {mention.url && (
                      <a
                        href={mention.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 inline-flex items-center gap-1 text-xs text-purple-300 hover:text-purple-200"
                      >
                        Open on X <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
