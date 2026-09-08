/**
 * The weekly posting slots.
 *
 * A grid of weekday columns; click to add a time, click a chip to remove it.
 * Saved as a whole week rather than slot by slot, because a half-applied
 * change would leave a workspace posting at times nobody chose.
 */
import { useCallback, useEffect, useState } from "react";
import { Clock, Plus, Save, X } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { showError, showSuccess } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { detailFrom, schedulingApi, WEEKDAYS, type QueueSlot } from "@/lib/scheduling";

interface Draft {
  weekday: number;
  time_local: string;
}

export function QueueSlotsEditor({
  accountId,
  timezone,
  onSaved,
}: {
  accountId: string;
  timezone?: string;
  onSaved?: () => void;
}) {
  const [slots, setSlots] = useState<Draft[]>([]);
  const [newTime, setNewTime] = useState("10:00");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await schedulingApi.slots(accountId);
      setSlots(
        rows
          .filter((r: QueueSlot) => r.is_active)
          .map((r) => ({ weekday: r.weekday, time_local: r.time_local.slice(0, 5) }))
      );
      setDirty(false);
    } catch {
      showError("Could not load the posting slots.");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    load();
  }, [load]);

  const add = (weekday: number) => {
    const exists = slots.some(
      (s) => s.weekday === weekday && s.time_local === newTime
    );
    if (exists) {
      showError("That slot is already in the week.");
      return;
    }
    setSlots((prev) => [...prev, { weekday, time_local: newTime }]);
    setDirty(true);
  };

  const remove = (weekday: number, time: string) => {
    setSlots((prev) =>
      prev.filter((s) => !(s.weekday === weekday && s.time_local === time))
    );
    setDirty(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await schedulingApi.saveSlots(
        accountId,
        slots.map((s) => ({
          weekday: s.weekday,
          time_local: `${s.time_local}:00`,
          is_active: true,
        }))
      );
      setDirty(false);
      showSuccess(
        slots.length
          ? `Saved ${slots.length} slot${slots.length === 1 ? "" : "s"} a week.`
          : "Cleared the posting schedule."
      );
      onSaved?.();
    } catch (err) {
      showError(detailFrom(err, "Could not save the slots."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <GlassCard>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold" style={{ color: "var(--page-heading)" }}>
            Posting schedule
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: "var(--page-text-muted)" }}>
            When this workspace posts. "Add to queue" drops a post into the next
            free slot.
            {timezone ? (
              <>
                {" "}
                Times are {timezone} — they stay put when the clocks change.
              </>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" style={{ color: "var(--page-text-muted)" }} />
            <input
              type="time"
              value={newTime}
              onChange={(e) => setNewTime(e.target.value)}
              className="rounded-lg px-2 py-1 text-xs tabular-nums"
              style={{
                backgroundColor: "var(--input-bg)",
                color: "var(--page-text)",
                border: "1px solid var(--surface-border)",
              }}
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            loading={saving}
            disabled={!dirty}
            icon={<Save className="h-3.5 w-3.5" />}
            onClick={save}
          >
            Save week
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="py-6 text-center text-sm" style={{ color: "var(--page-text-muted)" }}>
          Loading…
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {WEEKDAYS.map((day) => {
            const times = slots
              .filter((s) => s.weekday === day.value)
              .map((s) => s.time_local)
              .sort();
            return (
              <div
                key={day.value}
                className="rounded-xl p-2"
                style={{
                  backgroundColor: "var(--sidebar-hover-bg)",
                  border: "1px solid var(--surface-border)",
                }}
              >
                <p
                  className="mb-2 text-center text-xs font-medium"
                  style={{ color: "var(--page-text-secondary)" }}
                >
                  {day.short}
                </p>
                <div className="space-y-1">
                  {times.map((time) => (
                    <button
                      key={time}
                      onClick={() => remove(day.value, time)}
                      title="Remove this slot"
                      className="flex w-full items-center justify-center gap-1 rounded-md px-1.5 py-1 text-xs tabular-nums transition-colors hover:opacity-70"
                      style={{
                        backgroundColor: "rgba(109,94,246,0.16)",
                        color: "var(--page-heading)",
                      }}
                    >
                      {time}
                      <X className="h-3 w-3 opacity-60" />
                    </button>
                  ))}
                  <button
                    onClick={() => add(day.value)}
                    className={cn(
                      "flex w-full items-center justify-center rounded-md py-1 text-xs transition-colors hover:opacity-70"
                    )}
                    style={{ color: "var(--page-text-muted)" }}
                    title={`Add ${newTime} on ${day.label}`}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {slots.length === 0 && !loading && (
        <p className="mt-4 text-center text-xs" style={{ color: "var(--page-text-muted)" }}>
          No slots yet. Until there are, "add to queue" has nowhere to put a post.
        </p>
      )}
    </GlassCard>
  );
}

export default QueueSlotsEditor;
