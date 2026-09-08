/**
 * "Suggested times" chips for the composer.
 *
 * The chips look different depending on whether they came from this account's
 * own history or from the platform's usual posting times, and the label says
 * which. That distinction is the entire point: the heatmap this replaced was
 * `Math.random()` presented as measurement, and a user could not tell.
 */
import { useEffect, useState } from "react";
import { Clock, Info, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { fetchSuggestedSlots, type SlotSuggestion } from "@/lib/bestTimes";

export function SuggestedTimes({
  accountId,
  socialAccountId,
  onPick,
}: {
  accountId: string | null;
  socialAccountId?: string | null;
  /** Receives the local wall-clock date and time, already on the workspace's
   *  clock — the caller must not re-derive it through a Date. */
  onPick: (date: string, time: string) => void;
}) {
  const [slots, setSlots] = useState<SlotSuggestion[]>([]);
  const [source, setSource] = useState<string>("default");
  const [explanation, setExplanation] = useState("");

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    fetchSuggestedSlots(accountId, socialAccountId)
      .then((data) => {
        if (cancelled) return;
        setSlots(data.slots);
        setSource(data.source);
        setExplanation(data.explanation);
      })
      .catch(() => {
        /* Suggestions are a convenience; the composer still schedules. */
      });
    return () => {
      cancelled = true;
    };
  }, [accountId, socialAccountId]);

  if (!slots.length) return null;

  const measured = source === "observed";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        {measured ? (
          <Sparkles className="h-3.5 w-3.5" style={{ color: "var(--accent-purple)" }} />
        ) : (
          <Info className="h-3.5 w-3.5" style={{ color: "var(--page-text-muted)" }} />
        )}
        <span className="text-xs font-medium" style={{ color: "var(--page-text-secondary)" }}>
          {measured ? "Suggested from your results" : "Typical posting times"}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {slots.map((slot) => {
          const [date, time] = slot.local.split("T");
          return (
            <button
              key={slot.run_at}
              type="button"
              onClick={() => onPick(date, time)}
              title={
                slot.observed
                  ? `${slot.posts} posts here, averaging ${slot.score} interactions`
                  : "A usual time for this platform, not your own data"
              }
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors hover:opacity-80",
                // Measured suggestions are visually stronger than conventions.
                slot.observed
                  ? "border border-purple-500/30"
                  : "border border-dashed"
              )}
              style={{
                backgroundColor: slot.observed
                  ? "rgba(109,94,246,0.14)"
                  : "var(--sidebar-hover-bg)",
                color: slot.observed ? "var(--page-heading)" : "var(--page-text-secondary)",
                borderColor: slot.observed ? undefined : "var(--surface-border)",
              }}
            >
              <Clock className="h-3 w-3 opacity-70" />
              {slot.label}
              {slot.observed && slot.score !== null && (
                <span className="opacity-60">· {slot.score}</span>
              )}
            </button>
          );
        })}
      </div>

      <p className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>
        {explanation}
      </p>
    </div>
  );
}

export default SuggestedTimes;
