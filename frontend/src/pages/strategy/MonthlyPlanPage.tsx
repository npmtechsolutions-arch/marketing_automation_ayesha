import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CalendarDays, Check, Sparkles } from "lucide-react";

import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import api, { getAccountId } from "@/lib/api";

/** The AI manager's monthly plan, for review.
 *
 *  It proposes; a person disposes. Nothing on this screen publishes or
 *  schedules — "Accept selected" creates drafts, or posts in review where the
 *  workspace requires approval, and each one still needs a human to put it out.
 *  The button says so, because a reviewer should not have to infer it.
 *
 *  Every proposal shows **where its timing came from**: an observed slot,
 *  derived from posts this account actually published and measured, or a
 *  platform default. Those are different claims and only one of them is about
 *  the customer, so they do not get the same badge.
 */

interface PlanItem {
  id: string;
  scheduled_local: string;
  scheduled_at: string;
  target_account_ids: string[];
  content: string;
  hashtags: string[];
  rationale: string | null;
  /** "observed" | "default" — the field to read before believing the timing. */
  slot_source: string;
  status: string;
  post_id: string | null;
}

interface Plan {
  id: string;
  month: string;
  goal: string;
  status: string;
  grounding: {
    timezone?: string;
    connections?: { platform: string; account_name: string; social_account_id: string }[];
    slots?: Record<string, { source: string; explanation: string }>;
    past_performance?: { topics: string[]; explanation: string };
  } | null;
  provider: string | null;
  items: PlanItem[];
}

const GOALS = [
  { value: "awareness", label: "Awareness" },
  { value: "engagement", label: "Engagement" },
  { value: "traffic", label: "Traffic" },
  { value: "leads", label: "Leads" },
];

function firstOfNextMonth(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth() + 1, 1)
    .toISOString()
    .slice(0, 10);
}

export default function MonthlyPlanPage() {
  const [month, setMonth] = useState(firstOfNextMonth());
  const [goal, setGoal] = useState("awareness");
  const [cadence, setCadence] = useState<Record<string, number>>({});
  const [topicHints, setTopicHints] = useState("");
  const [connections, setConnections] = useState<
    { platform: string; account_name: string; social_account_id: string }[]
  >([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [accepting, setAccepting] = useState(false);

  const loadConnections = async () => {
    const accountId = await getAccountId();
    if (!accountId) return;
    try {
      const res: any = await api.get(`/accounts/${accountId}/social-accounts/`);
      const items = (res.data ?? res)?.items ?? [];
      setConnections(
        items.map((s: any) => ({
          platform: (s.platform_slug ?? s.platform ?? "").toLowerCase(),
          account_name: s.account_name,
          social_account_id: s.id,
        }))
      );
    } catch {
      // The generator reports the same problem more usefully; no toast here.
    }
  };

  useEffect(() => { loadConnections(); }, []);

  const generate = async () => {
    const accountId = await getAccountId();
    if (!accountId) return;
    setGenerating(true);
    setPlan(null);
    try {
      const res: any = await api.post(`/accounts/${accountId}/ai/monthly-plan`, {
        month,
        goal,
        cadence,
        topic_hints: topicHints.trim() || null,
      });
      const created: Plan = res.data ?? res;
      setPlan(created);
      // Nothing pre-selected: accepting is a decision, not a default.
      setSelected(new Set());
    } catch (err: any) {
      showError(err?.response?.data?.detail || "Could not generate a plan.");
    } finally {
      setGenerating(false);
    }
  };

  const acceptSelected = async () => {
    const accountId = await getAccountId();
    if (!accountId || !plan || selected.size === 0) return;
    setAccepting(true);
    try {
      const res: any = await api.post(
        `/accounts/${accountId}/ai/monthly-plan/${plan.id}/accept`,
        { item_ids: [...selected] }
      );
      const body = res.data ?? res;
      showSuccess(
        body.submitted_for_review
          ? `${body.created.length} post(s) created and sent for review.`
          : `${body.created.length} draft(s) created. Nothing has been published.`
      );
      const reread: any = await api.get(
        `/accounts/${accountId}/ai/monthly-plan/${plan.id}`
      );
      setPlan(reread.data ?? reread);
      setSelected(new Set());
    } catch (err: any) {
      // The reservation is atomic, so a refusal means nothing was created.
      showError(
        err?.response?.data?.detail ||
          "Could not accept those proposals. Nothing was created."
      );
    } finally {
      setAccepting(false);
    }
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const proposals = plan?.items.filter((i) => i.status === "proposed") ?? [];
  const accepted = plan?.items.filter((i) => i.status === "accepted") ?? [];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
            Monthly plan
          </h1>
          <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
            A month of proposals, built from this workspace's own posting history.
            Nothing here is published or scheduled until you accept it.
          </p>
        </div>

        <GlassCard>
          <div className="grid gap-4 md:grid-cols-3">
            <Input
              label="Month"
              type="date"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            />
            <Select label="Goal" options={GOALS} value={goal} onChange={setGoal} />
            <Input
              label="Topics to cover (optional)"
              value={topicHints}
              onChange={(e) => setTopicHints(e.target.value)}
              placeholder="product launch, hiring"
            />
          </div>

          <div className="mt-5">
            <p className="text-xs font-medium uppercase tracking-wider mb-2"
               style={{ color: "var(--page-text-muted)" }}>
              Posts per week
            </p>
            {connections.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--page-text-muted)" }}>
                No connected accounts yet. A plan is built from the platforms this
                workspace actually posts to, so connect one first.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {connections.map((c) => (
                  <div key={c.social_account_id}
                       className="flex items-center justify-between rounded-xl px-3 py-2"
                       style={{ backgroundColor: "var(--sidebar-hover-bg)", border: "1px solid var(--surface-border)" }}>
                    <span className="text-sm truncate" style={{ color: "var(--page-text)" }}>
                      {c.account_name}
                    </span>
                    <input
                      type="number"
                      min={0}
                      max={21}
                      value={cadence[c.platform] ?? 0}
                      onChange={(e) =>
                        setCadence((prev) => ({
                          ...prev,
                          [c.platform]: Number(e.target.value),
                        }))
                      }
                      className="w-16 rounded-lg px-2 py-1 text-sm text-right"
                      style={{ backgroundColor: "var(--page-bg)", border: "1px solid var(--surface-border)", color: "var(--page-text)" }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button
              variant="primary"
              loading={generating}
              disabled={connections.length === 0}
              icon={<Sparkles className="w-4 h-4" />}
              onClick={generate}
            >
              {generating ? "Generating…" : "Generate plan"}
            </Button>
            <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
              Uses 5 of your monthly AI requests.
            </span>
          </div>
        </GlassCard>

        {plan && (
          <>
            {/* What the plan was built from. A reviewer should be able to check
                the basis of a proposal, not just the proposal. */}
            <GlassCard>
              <p className="text-xs font-medium uppercase tracking-wider mb-2"
                 style={{ color: "var(--page-text-muted)" }}>
                What this plan is based on
              </p>
              <ul className="space-y-1.5 text-sm" style={{ color: "var(--page-text-secondary)" }}>
                {Object.entries(plan.grounding?.slots ?? {}).map(([platform, info]) => (
                  <li key={platform}>
                    <Badge variant={info.source === "observed" ? "success" : "default"} size="sm">
                      {info.source === "observed" ? "observed" : "default times"}
                    </Badge>{" "}
                    <span className="capitalize">{platform}</span> — {info.explanation}
                  </li>
                ))}
                <li>{plan.grounding?.past_performance?.explanation}</li>
                {plan.grounding?.timezone && (
                  <li>Times are on the workspace's clock ({plan.grounding.timezone}).</li>
                )}
              </ul>
            </GlassCard>

            <div className="flex items-center justify-between">
              <p className="text-sm" style={{ color: "var(--page-text-secondary)" }}>
                {proposals.length} proposal{proposals.length === 1 ? "" : "s"}
                {accepted.length > 0 && ` · ${accepted.length} already accepted`}
              </p>
              <Button
                variant="primary"
                loading={accepting}
                disabled={selected.size === 0}
                icon={<Check className="w-4 h-4" />}
                onClick={acceptSelected}
              >
                {/* Says what it does. "Accept" alone reads like "publish". */}
                Create {selected.size || ""} draft{selected.size === 1 ? "" : "s"}
              </Button>
            </div>

            <div className="space-y-3">
              {proposals.map((item) => {
                const isSelected = selected.has(item.id);
                const when = new Date(item.scheduled_local);
                return (
                  <motion.div key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                    <GlassCard
                      padding="sm"
                      className={cn(isSelected && "!border-purple-500/40")}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggle(item.id)}
                          aria-label={`Select the post for ${when.toLocaleString()}`}
                          className="mt-1 w-4 h-4 accent-purple-600 cursor-pointer"
                        />
                        <div className="flex-1 min-w-0 space-y-1.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="flex items-center gap-1.5 text-xs"
                                  style={{ color: "var(--page-text-secondary)" }}>
                              <CalendarDays className="w-3.5 h-3.5" />
                              {when.toLocaleString(undefined, {
                                weekday: "short", day: "numeric", month: "short",
                                hour: "2-digit", minute: "2-digit",
                              })}
                            </span>
                            {/* Observed and default are not the same claim. */}
                            <Badge
                              variant={item.slot_source === "observed" ? "success" : "default"}
                              size="sm"
                            >
                              {item.slot_source === "observed"
                                ? "observed slot"
                                : "default time"}
                            </Badge>
                          </div>
                          <p className="text-sm whitespace-pre-wrap"
                             style={{ color: "var(--page-text)" }}>
                            {item.content}
                          </p>
                          {item.hashtags.length > 0 && (
                            <p className="text-xs" style={{ color: "#a78bfa" }}>
                              {item.hashtags.map((h) => `#${h}`).join(" ")}
                            </p>
                          )}
                          {item.rationale && (
                            <p className="text-xs italic" style={{ color: "var(--page-text-muted)" }}>
                              {item.rationale}
                            </p>
                          )}
                        </div>
                      </div>
                    </GlassCard>
                  </motion.div>
                );
              })}
            </div>

            {accepted.length > 0 && (
              <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                {accepted.length} proposal{accepted.length === 1 ? " has" : "s have"} been
                turned into drafts. They are in the content calendar, unpublished.
              </p>
            )}

            {proposals.length === 0 && accepted.length === 0 && (
              <GlassCard>
                <p className="text-sm" style={{ color: "var(--page-text-muted)" }}>
                  The generator produced no proposals for this month. That usually
                  means the cadence leaves no slots in the days remaining.
                </p>
              </GlassCard>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
