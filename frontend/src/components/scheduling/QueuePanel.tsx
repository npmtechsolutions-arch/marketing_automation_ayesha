/**
 * The queue, on the calendar: the week's slots, what is coming up, and any
 * recurring schedules running.
 */
import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Pause, Play, Repeat, Trash2 } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/Badge";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import QueueSlotsEditor from "./QueueSlotsEditor";
import {
  detailFrom,
  schedulingApi,
  type QueueState,
  type RecurringSchedule,
} from "@/lib/scheduling";

export function QueuePanel({ accountId }: { accountId: string }) {
  const [state, setState] = useState<QueueState | null>(null);
  const [schedules, setSchedules] = useState<RecurringSchedule[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [queue, recurring] = await Promise.allSettled([
      schedulingApi.upcoming(accountId, 12),
      schedulingApi.listRecurring(accountId),
    ]);
    if (queue.status === "fulfilled") setState(queue.value);
    if (recurring.status === "fulfilled") setSchedules(recurring.value);
    setLoading(false);
  }, [accountId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (schedule: RecurringSchedule) => {
    const next = schedule.status === "active" ? "paused" : "active";
    try {
      await schedulingApi.updateRecurring(accountId, schedule.id, { status: next });
      showSuccess(next === "active" ? "Schedule resumed." : "Schedule paused.");
      await load();
    } catch (err) {
      showError(detailFrom(err, "Could not update the schedule."));
    }
  };

  const cancel = async (schedule: RecurringSchedule) => {
    if (
      !window.confirm(
        "Stop this recurring schedule? Posts it already created are kept."
      )
    ) {
      return;
    }
    try {
      await schedulingApi.cancelRecurring(accountId, schedule.id);
      showSuccess("Schedule stopped.");
      await load();
    } catch {
      showError("Could not stop the schedule.");
    }
  };

  return (
    <div className="space-y-6">
      <QueueSlotsEditor
        accountId={accountId}
        timezone={state?.timezone}
        onSaved={load}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GlassCard>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
              Next slots
            </h3>
            {state?.configured && (
              <span className="text-xs" style={{ color: "var(--page-text-muted)" }}>
                {state.slots_per_week}/week · {state.queued} queued
              </span>
            )}
          </div>

          {loading ? (
            <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
              Loading…
            </p>
          ) : !state?.slots.length ? (
            <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
              Add slots above and they will appear here.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {state.slots.map((slot) => (
                <li
                  key={slot.run_at}
                  className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                  style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
                >
                  <CalendarClock
                    className="h-3.5 w-3.5 shrink-0"
                    style={{ color: "var(--page-text-muted)" }}
                  />
                  <span className="tabular-nums" style={{ color: "var(--page-text)" }}>
                    {slot.local_datetime.slice(0, 16).replace("T", " ")}
                  </span>
                  {slot.shifted_for_dst && (
                    // Once a year a slot inside the spring-forward gap really
                    // does publish an hour later. Saying so beats looking wrong.
                    <Badge variant="warning">clocks change</Badge>
                  )}
                  <span
                    className={cn("ml-auto text-xs")}
                    style={{
                      color: slot.taken ? "var(--page-text-muted)" : "#10b981",
                    }}
                  >
                    {slot.taken ? "taken" : "free"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>

        <GlassCard>
          <h3 className="mb-3 text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Repeating posts
          </h3>
          {!schedules.length ? (
            <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
              None yet. Set a post to repeat from the composer.
            </p>
          ) : (
            <ul className="space-y-2">
              {schedules.map((schedule) => (
                <li
                  key={schedule.id}
                  className="rounded-lg px-3 py-2"
                  style={{ backgroundColor: "var(--sidebar-hover-bg)" }}
                >
                  <div className="flex items-center gap-2">
                    <Repeat className="h-3.5 w-3.5" style={{ color: "var(--accent-purple)" }} />
                    <span className="truncate text-sm" style={{ color: "var(--page-text)" }}>
                      {schedule.name || schedule.summary}
                    </span>
                    <Badge
                      variant={
                        schedule.status === "active"
                          ? "success"
                          : schedule.status === "paused"
                            ? "warning"
                            : "default"
                      }
                    >
                      {schedule.status}
                    </Badge>
                    <div className="ml-auto flex items-center gap-1">
                      {schedule.status !== "cancelled" &&
                        schedule.status !== "completed" && (
                          <button
                            onClick={() => toggle(schedule)}
                            title={schedule.status === "active" ? "Pause" : "Resume"}
                            style={{ color: "var(--page-text-muted)" }}
                          >
                            {schedule.status === "active" ? (
                              <Pause className="h-3.5 w-3.5" />
                            ) : (
                              <Play className="h-3.5 w-3.5" />
                            )}
                          </button>
                        )}
                      <button
                        onClick={() => cancel(schedule)}
                        title="Stop"
                        style={{ color: "var(--page-text-muted)" }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs" style={{ color: "var(--page-text-muted)" }}>
                    {schedule.next_run_at
                      ? `Next ${schedule.next_run_at.slice(0, 16).replace("T", " ")} UTC`
                      : "No further runs"}
                    {" · "}
                    {schedule.occurrence_count} published
                    {schedule.max_occurrences ? ` of ${schedule.max_occurrences}` : ""}
                  </p>
                  {schedule.last_error && (
                    <p className="mt-1 text-xs" style={{ color: "#f43f5e" }}>
                      {schedule.last_error}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </GlassCard>
      </div>
    </div>
  );
}

export default QueuePanel;
