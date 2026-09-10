/**
 * The unified inbox: threads on the left, conversation on the right.
 *
 * The part worth being careful about is what the UI says when a platform
 * cannot do something. An empty list and "this platform has no message API"
 * look identical to a reader and mean opposite things, so the capabilities are
 * fetched and stated plainly rather than left to inference.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AtSign, Check, Info, MessageCircle, MessageSquare, RefreshCw,
  Send, StickyNote, Tag,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import api, { getAccountIdSync } from "@/lib/api";
import { detailFrom } from "@/lib/scheduling";
import { platformColor } from "@/pages/analytics/chart";
import {
  canReply, inboxApi, TYPE_LABELS,
  type ConnectionCapability, type Thread, type ThreadDetail,
  type ThreadFilters, type ThreadType,
} from "@/lib/inbox";

const TYPE_ICON: Record<ThreadType, React.ReactNode> = {
  comment: <MessageSquare className="h-3.5 w-3.5" />,
  dm: <MessageCircle className="h-3.5 w-3.5" />,
  mention: <AtSign className="h-3.5 w-3.5" />,
};

interface Member { user_id: string; name: string }

export default function InboxPage() {
  const accountId = getAccountIdSync();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [capabilities, setCapabilities] = useState<ConnectionCapability[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selected, setSelected] = useState<ThreadDetail | null>(null);
  const [filters, setFilters] = useState<ThreadFilters>({ status: "open" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [isNote, setIsNote] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const data = await inboxApi.list(accountId, filters);
      setThreads(data.threads);
      setCounts(data.counts);
    } catch (err) {
      showError(detailFrom(err, "Could not load the inbox."));
    } finally {
      setLoading(false);
    }
  }, [accountId, filters]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!accountId) return;
    inboxApi.capabilities(accountId).then(setCapabilities).catch(() => {});
    interface RawMember {
      user_id?: string;
      invitation_email?: string;
      user?: { id?: string; full_name?: string };
    }
    api
      .get<{ items?: RawMember[] } | RawMember[]>(
        // The teams router is mounted at /accounts/{id}/team and lists its
        // members at the root. This asked for /teams/members, which 404'd on
        // every inbox load -- so the assignee dropdown has never had anyone in
        // it, and "assign to a teammate" looked available and did nothing.
        `/accounts/${accountId}/team/`
      )
      .then((r) => {
        const payload = r.data;
        const items: RawMember[] = Array.isArray(payload)
          ? payload
          : payload?.items ?? [];
        setMembers(
          items
            .map((m) => ({
              user_id: m.user_id ?? m.user?.id ?? "",
              name: m.user?.full_name ?? m.invitation_email ?? "Member",
            }))
            .filter((m) => m.user_id)
        );
      })
      .catch(() => {
        /* The inbox still works; the assignee picker is just empty. */
      });
  }, [accountId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [selected?.messages.length]);

  const open = async (thread: Thread) => {
    if (!accountId) return;
    try {
      setSelected(await inboxApi.thread(accountId, thread.id));
      // Opening marks it read server-side; mirror it locally rather than
      // refetching the whole list for one number.
      setThreads((prev) =>
        prev.map((t) => (t.id === thread.id ? { ...t, unread_count: 0 } : t))
      );
    } catch (err) {
      showError(detailFrom(err, "Could not open that thread."));
    }
  };

  const send = async () => {
    if (!accountId || !selected || !draft.trim()) return;
    setBusy(true);
    try {
      const message = isNote
        ? await inboxApi.note(accountId, selected.id, draft.trim())
        : await inboxApi.reply(accountId, selected.id, draft.trim());
      setSelected({ ...selected, messages: [...selected.messages, message] });
      setDraft("");
      showSuccess(isNote ? "Note added." : "Reply sent.");
      if (!isNote) await load();
    } catch (err) {
      showError(detailFrom(err, "Could not send that."));
    } finally {
      setBusy(false);
    }
  };

  const mutate = async (fn: () => Promise<Thread>) => {
    try {
      const updated = await fn();
      setSelected((prev) => (prev ? { ...prev, ...updated } : prev));
      setThreads((prev) => prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)));
    } catch (err) {
      showError(detailFrom(err, "That did not work."));
    }
  };

  const syncNow = async () => {
    if (!accountId) return;
    setBusy(true);
    try {
      const result = await inboxApi.syncNow(accountId);
      showSuccess(
        result.new_messages
          ? `${result.new_messages} new message${result.new_messages === 1 ? "" : "s"}.`
          : "Nothing new."
      );
      await load();
    } catch (err) {
      showError(detailFrom(err, "Sync failed."));
    } finally {
      setBusy(false);
    }
  };

  // What every connected platform genuinely cannot do, stated once rather than
  // left as an empty list the reader has to interpret.
  const gaps = useMemo(() => {
    const missing: string[] = [];
    for (const connection of capabilities) {
      for (const [kind, ok] of Object.entries(connection.supports)) {
        if (!ok) missing.push(`${connection.platform} ${TYPE_LABELS[kind as ThreadType].toLowerCase()}s`);
      }
    }
    return missing;
  }, [capabilities]);

  const replyAllowed = selected ? canReply(selected) : false;

  return (
    <DashboardLayout>
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Inbox
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Comments, messages and mentions across every connected account.
            </p>
          </div>
          <Button variant="secondary" size="sm" loading={busy}
                  icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={syncNow}>
            Check now
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(["open", "resolved"] as const).map((value) => (
            <button key={value}
              onClick={() => setFilters((f) => ({ ...f, status: value }))}
              className={cn("rounded-lg px-3 py-1.5 text-xs capitalize transition-colors",
                filters.status === value && "bg-purple-500/20 text-purple-300")}
              style={filters.status === value ? undefined
                : { color: "var(--page-text-secondary)", backgroundColor: "var(--sidebar-hover-bg)" }}>
              {value} ({counts[value] ?? 0})
            </button>
          ))}
          <select
            value={filters.platform ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, platform: e.target.value || undefined }))}
            className="rounded-lg px-2 py-1.5 text-xs"
            style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
          >
            <option value="">All platforms</option>
            {[...new Set(capabilities.map((c) => c.platform))].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <select
            value={filters.type ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, type: (e.target.value || undefined) as ThreadType }))}
            className="rounded-lg px-2 py-1.5 text-xs"
            style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
          >
            <option value="">All kinds</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select
            value={filters.unassigned ? "unassigned" : filters.assigned_to ?? ""}
            onChange={(e) => {
              const value = e.target.value;
              setFilters((f) => ({
                ...f,
                unassigned: value === "unassigned",
                assigned_to: value && value !== "unassigned" ? value : undefined,
              }));
            }}
            className="rounded-lg px-2 py-1.5 text-xs"
            style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
          >
            <option value="">Anyone</option>
            <option value="unassigned">Unassigned</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>{m.name}</option>
            ))}
          </select>
          <input
            placeholder="tag"
            value={filters.tag ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, tag: e.target.value || undefined }))}
            className="w-24 rounded-lg px-2 py-1.5 text-xs"
            style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
          />
        </div>

        {gaps.length > 0 && (
          <p className="flex items-start gap-1.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Not available on these platforms' APIs, so nothing will appear for them:{" "}
            {gaps.join(", ")}.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
          <GlassCard padding="sm">
            {loading ? (
              <Skeleton variant="card" height="360px" />
            ) : threads.length === 0 ? (
              <EmptyState icon={<MessageSquare className="h-6 w-6" />} title="Nothing here"
                description="No threads match these filters." />
            ) : (
              <ul className="max-h-[62vh] space-y-1 overflow-auto">
                {threads.map((thread) => (
                  <li key={thread.id}>
                    <button onClick={() => open(thread)}
                      className={cn("w-full rounded-xl px-3 py-2.5 text-left transition-colors",
                        selected?.id === thread.id && "bg-purple-500/10")}
                      style={selected?.id === thread.id ? undefined : { backgroundColor: "transparent" }}>
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 shrink-0 rounded-full"
                              style={{ backgroundColor: platformColor(thread.platform ?? "") }} />
                        <span className="truncate text-sm font-medium" style={{ color: "var(--page-heading)" }}>
                          {thread.participant}
                        </span>
                        <span style={{ color: "var(--page-text-muted)" }}>
                          {TYPE_ICON[thread.type]}
                        </span>
                        {thread.unread_count > 0 && (
                          <span className="ml-auto rounded-full px-1.5 text-[10px]"
                                style={{ backgroundColor: "var(--accent-purple)", color: "#fff" }}>
                            {thread.unread_count}
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 truncate text-xs" style={{ color: "var(--page-text-muted)" }}>
                        {thread.last_message_preview ?? "—"}
                      </p>
                      {thread.tags.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {thread.tags.map((tag) => (
                            <span key={tag} className="rounded px-1.5 text-[10px]"
                                  style={{ backgroundColor: "var(--sidebar-hover-bg)", color: "var(--page-text-secondary)" }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>

          <GlassCard>
            {!selected ? (
              <EmptyState icon={<MessageCircle className="h-6 w-6" />} title="Pick a conversation"
                description="Choose a thread on the left to read and reply." />
            ) : (
              <div className="flex h-[62vh] flex-col">
                <div className="flex flex-wrap items-center gap-2 border-b pb-3"
                     style={{ borderColor: "var(--surface-border)" }}>
                  <span className="font-medium" style={{ color: "var(--page-heading)" }}>
                    {selected.participant}
                  </span>
                  <Badge variant="default">{TYPE_LABELS[selected.type]}</Badge>
                  {selected.permalink && (
                    <a href={selected.permalink} target="_blank" rel="noopener noreferrer"
                       className="text-xs" style={{ color: "var(--accent-purple)" }}>
                      View on {selected.platform}
                    </a>
                  )}
                  <div className="ml-auto flex items-center gap-2">
                    <select
                      value={selected.assigned_to ?? ""}
                      onChange={(e) => mutate(() =>
                        inboxApi.assign(accountId!, selected.id, e.target.value || null))}
                      className="rounded-lg px-2 py-1 text-xs"
                      style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                    >
                      <option value="">Unassigned</option>
                      {members.map((m) => (
                        <option key={m.user_id} value={m.user_id}>{m.name}</option>
                      ))}
                    </select>
                    <Button variant={selected.status === "resolved" ? "secondary" : "primary"}
                      size="sm" icon={<Check className="h-3.5 w-3.5" />}
                      onClick={() => mutate(() => inboxApi.setStatus(
                        accountId!, selected.id,
                        selected.status === "resolved" ? "open" : "resolved"))}>
                      {selected.status === "resolved" ? "Reopen" : "Resolve"}
                    </Button>
                  </div>
                </div>

                <div className="flex items-center gap-2 py-2">
                  <Tag className="h-3.5 w-3.5" style={{ color: "var(--page-text-muted)" }} />
                  <input
                    defaultValue={selected.tags.join(", ")}
                    onBlur={(e) => {
                      const tags = e.target.value.split(",").map((t) => t.trim()).filter(Boolean);
                      if (tags.join() !== selected.tags.join()) {
                        mutate(() => inboxApi.setTags(accountId!, selected.id, tags));
                      }
                    }}
                    placeholder="tags, comma separated"
                    className="flex-1 rounded-lg px-2 py-1 text-xs"
                    style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                  />
                </div>

                <div className="flex-1 space-y-3 overflow-auto py-3">
                  {selected.messages.map((message) => (
                    <div key={message.id}
                      className={cn("max-w-[78%] rounded-xl px-3 py-2",
                        message.direction === "outbound" && "ml-auto",
                        message.direction === "internal" && "mx-auto w-full max-w-full")}
                      style={{
                        backgroundColor:
                          message.direction === "internal"
                            ? "rgba(245,158,11,0.10)"
                            : message.direction === "outbound"
                              ? "rgba(109,94,246,0.16)"
                              : "var(--sidebar-hover-bg)",
                        border: message.direction === "internal"
                          ? "1px dashed rgba(245,158,11,0.4)" : undefined,
                      }}>
                      <div className="flex items-center gap-1.5">
                        {message.direction === "internal" && (
                          <StickyNote className="h-3 w-3" style={{ color: "#f59e0b" }} />
                        )}
                        <span className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>
                          {message.direction === "internal" ? "Internal note" : message.author}
                          {" · "}
                          {message.created_at.slice(0, 16).replace("T", " ")}
                        </span>
                      </div>
                      <p className="mt-0.5 whitespace-pre-wrap text-sm" style={{ color: "var(--page-text)" }}>
                        {message.body}
                      </p>
                    </div>
                  ))}
                  <div ref={bottom} />
                </div>

                <div className="border-t pt-3" style={{ borderColor: "var(--surface-border)" }}>
                  <div className="mb-2 flex items-center gap-2">
                    {[false, true].map((note) => (
                      <button key={String(note)} onClick={() => setIsNote(note)}
                        className={cn("rounded-lg px-2.5 py-1 text-xs transition-colors",
                          isNote === note && "bg-purple-500/20 text-purple-300")}
                        style={isNote === note ? undefined : { color: "var(--page-text-secondary)" }}>
                        {note ? "Internal note" : "Reply"}
                      </button>
                    ))}
                    {!isNote && !replyAllowed && (
                      <span className="flex items-center gap-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                        <Info className="h-3.5 w-3.5" />
                        Mentions are answered by posting publicly, not from here.
                      </span>
                    )}
                  </div>
                  <div className="flex items-end gap-2">
                    <textarea
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      rows={2}
                      disabled={!isNote && !replyAllowed}
                      placeholder={isNote ? "A note for your team…" : "Write a reply…"}
                      className="flex-1 rounded-xl px-3 py-2 text-sm disabled:opacity-50"
                      style={{ backgroundColor: "var(--input-bg)", color: "var(--page-text)", border: "1px solid var(--surface-border)" }}
                    />
                    <Button variant="primary" loading={busy}
                      disabled={!draft.trim() || (!isNote && !replyAllowed)}
                      icon={isNote ? <StickyNote className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                      onClick={send}>
                      {isNote ? "Add note" : "Send"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
