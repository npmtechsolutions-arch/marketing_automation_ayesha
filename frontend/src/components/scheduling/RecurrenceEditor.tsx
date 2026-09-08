/**
 * Building a repeat rule, with a preview of the dates it produces.
 *
 * The preview is not decoration. An RRULE is unreadable, and the only honest
 * way to show someone what a rule does is to list the dates. It is also where
 * a DST shift becomes visible: two consecutive rows with the same local time
 * and different UTC offsets look like a bug until you can see the offset
 * column explaining it.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, Repeat } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { showError } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import {
  buildRrule,
  detailFrom,
  localDateTime,
  schedulingApi,
  WEEKDAYS,
  type OccurrencePreview,
} from "@/lib/scheduling";

type Frequency = "daily" | "weekly" | "monthly";

export function RecurrenceEditor({
  accountId,
  postId,
  onCreated,
}: {
  accountId: string;
  postId: string | null;
  onCreated?: (scheduleId: string) => void;
}) {
  const [frequency, setFrequency] = useState<Frequency>("weekly");
  const [weekdays, setWeekdays] = useState<number[]>([0]);
  const [startDate, setStartDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [startTime, setStartTime] = useState("10:00");
  const [endMode, setEndMode] = useState<"never" | "count" | "until">("never");
  const [count, setCount] = useState("10");
  const [untilDate, setUntilDate] = useState("");

  const [preview, setPreview] = useState<OccurrencePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const rrule = buildRrule(frequency, weekdays);

  const body = useCallback(
    () => ({
      // A placeholder id is fine for previewing: the endpoint only needs a
      // post to exist when the schedule is actually created.
      template_post_id: postId ?? "00000000-0000-0000-0000-000000000000",
      rrule,
      starts_at_local: localDateTime(startDate, startTime),
      until_local:
        endMode === "until" && untilDate
          ? localDateTime(untilDate, "23:59")
          : null,
      max_occurrences: endMode === "count" ? Number(count) || null : null,
    }),
    [postId, rrule, startDate, startTime, endMode, untilDate, count]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await schedulingApi.previewRecurring(accountId, body());
        if (!cancelled) {
          setPreview(result);
          setPreviewError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setPreview(null);
          setPreviewError(detailFrom(err, "Could not preview that rule."));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accountId, body]);

  const toggleDay = (day: number) =>
    setWeekdays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );

  const create = async () => {
    if (!postId) {
      showError("Save the post first, then set it to repeat.");
      return;
    }
    setSaving(true);
    try {
      const schedule = await schedulingApi.createRecurring(accountId, body());
      onCreated?.(schedule.id);
    } catch (err) {
      showError(detailFrom(err, "Could not create the schedule."));
    } finally {
      setSaving(false);
    }
  };

  // Two rows an hour apart in UTC but identical in local time means the clocks
  // changed between them. Worth pointing at rather than leaving to look wrong.
  const offsets = new Set((preview?.occurrences ?? []).map((o) => o.utc_offset));
  const crossesDst = offsets.size > 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Repeat className="h-4 w-4" style={{ color: "var(--accent-purple)" }} />
        {(["daily", "weekly", "monthly"] as Frequency[]).map((option) => (
          <button
            key={option}
            onClick={() => setFrequency(option)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs capitalize transition-colors",
              frequency === option && "bg-purple-500/20 text-purple-300"
            )}
            style={
              frequency === option ? undefined : { color: "var(--page-text-secondary)" }
            }
          >
            {option}
          </button>
        ))}
      </div>

      {frequency === "weekly" && (
        <div className="flex flex-wrap gap-1.5">
          {WEEKDAYS.map((day) => (
            <button
              key={day.value}
              onClick={() => toggleDay(day.value)}
              className={cn(
                "rounded-lg px-2.5 py-1.5 text-xs transition-colors",
                weekdays.includes(day.value) && "bg-purple-500/20 text-purple-300"
              )}
              style={
                weekdays.includes(day.value)
                  ? undefined
                  : {
                      color: "var(--page-text-secondary)",
                      backgroundColor: "var(--sidebar-hover-bg)",
                    }
              }
            >
              {day.short}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
          Starting
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="mt-1 w-full rounded-lg px-2.5 py-1.5 text-sm"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
        </label>
        <label className="text-xs" style={{ color: "var(--page-text-secondary)" }}>
          At {preview?.timezone ? `(${preview.timezone})` : ""}
          <input
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="mt-1 w-full rounded-lg px-2.5 py-1.5 text-sm tabular-nums"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span style={{ color: "var(--page-text-secondary)" }}>Ends</span>
        {(["never", "count", "until"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setEndMode(mode)}
            className={cn(
              "rounded-lg px-2.5 py-1.5 transition-colors",
              endMode === mode && "bg-purple-500/20 text-purple-300"
            )}
            style={endMode === mode ? undefined : { color: "var(--page-text-muted)" }}
          >
            {mode === "never" ? "Never" : mode === "count" ? "After N posts" : "On a date"}
          </button>
        ))}
        {endMode === "count" && (
          <input
            type="number"
            min={1}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            className="w-20 rounded-lg px-2 py-1 text-xs tabular-nums"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
        )}
        {endMode === "until" && (
          <input
            type="date"
            value={untilDate}
            onChange={(e) => setUntilDate(e.target.value)}
            className="rounded-lg px-2 py-1 text-xs"
            style={{
              backgroundColor: "var(--input-bg)",
              color: "var(--page-text)",
              border: "1px solid var(--surface-border)",
            }}
          />
        )}
      </div>

      <div
        className="rounded-xl p-3"
        style={{
          backgroundColor: "var(--sidebar-hover-bg)",
          border: "1px solid var(--surface-border)",
        }}
      >
        <div className="mb-2 flex items-center gap-2">
          <CalendarClock className="h-3.5 w-3.5" style={{ color: "var(--page-text-muted)" }} />
          <span className="text-xs font-medium" style={{ color: "var(--page-text-secondary)" }}>
            Next dates
          </span>
        </div>
        {previewError ? (
          <p className="text-xs" style={{ color: "#f43f5e" }}>
            {previewError}
          </p>
        ) : !preview?.occurrences.length ? (
          <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>
            That rule produces no dates. Check the start and the end condition.
          </p>
        ) : (
          <>
            <ul className="space-y-1">
              {preview.occurrences.slice(0, 6).map((occurrence) => (
                <li
                  key={occurrence.run_at}
                  className="flex items-center gap-3 text-xs tabular-nums"
                  style={{ color: "var(--page-text)" }}
                >
                  <span>{occurrence.local.slice(0, 16).replace("T", " ")}</span>
                  <span className="ml-auto" style={{ color: "var(--page-text-muted)" }}>
                    UTC{occurrence.utc_offset.replace(/(\d{2})(\d{2})/, "$1:$2")}
                  </span>
                </li>
              ))}
            </ul>
            {crossesDst && (
              <p
                className="mt-2 flex items-start gap-1.5 text-[11px]"
                style={{ color: "var(--page-text-muted)" }}
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                The clocks change during this run. The local time stays the same,
                which is why the UTC offset shifts.
              </p>
            )}
          </>
        )}
      </div>

      <Button
        variant="primary"
        loading={saving}
        disabled={!postId || !preview?.occurrences.length}
        icon={<Repeat className="h-4 w-4" />}
        onClick={create}
        fullWidth
      >
        Repeat this post
      </Button>
    </div>
  );
}

export default RecurrenceEditor;
