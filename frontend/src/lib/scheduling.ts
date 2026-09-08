/**
 * Queue slots and recurring schedules.
 *
 * One rule runs through this file: **times sent to the server are local
 * wall-clock readings without an offset.** `2026-03-09T10:00:00` means "ten in
 * the morning on the workspace's clock", and the server supplies the zone.
 *
 * The tempting alternative — `new Date(...).toISOString()` — converts through
 * the *browser's* timezone, so an agency in London scheduling for a Sydney
 * workspace would set a time eleven hours out, and the error would move by an
 * hour twice a year when either side's clocks changed.
 */
import api from "@/lib/api";

export interface QueueSlot {
  id: string;
  /** 0 = Monday … 6 = Sunday, matching the backend and Python's weekday(). */
  weekday: number;
  time_local: string;
  is_active: boolean;
}

export interface UpcomingSlot {
  slot_id: string;
  weekday: number;
  local_time: string;
  local_datetime: string;
  run_at: string;
  taken: boolean;
  /** True for the once-a-year slot that falls in the spring-forward gap. */
  shifted_for_dst: boolean;
  ambiguous_for_dst: boolean;
}

export interface QueueState {
  timezone: string;
  slots: UpcomingSlot[];
  configured: boolean;
  slots_per_week: number;
  queued: number;
  next_free: string | null;
}

export interface RecurringSchedule {
  id: string;
  name: string | null;
  template_post_id: string;
  rrule: string;
  summary: string;
  timezone: string;
  starts_at_local: string;
  until_local: string | null;
  max_occurrences: number | null;
  occurrence_count: number;
  status: "active" | "paused" | "completed" | "cancelled";
  next_run_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
}

export interface OccurrencePreview {
  timezone: string;
  summary: string;
  occurrences: { run_at: string; local: string; utc_offset: string }[];
}

export const WEEKDAYS = [
  { value: 0, short: "Mon", label: "Monday" },
  { value: 1, short: "Tue", label: "Tuesday" },
  { value: 2, short: "Wed", label: "Wednesday" },
  { value: 3, short: "Thu", label: "Thursday" },
  { value: 4, short: "Fri", label: "Friday" },
  { value: 5, short: "Sat", label: "Saturday" },
  { value: 6, short: "Sun", label: "Sunday" },
];

const base = (accountId: string) => `/accounts/${accountId}/scheduling`;

export const schedulingApi = {
  slots: (accountId: string) =>
    api.get<QueueSlot[]>(`${base(accountId)}/queue/slots`).then((r) => r.data),

  saveSlots: (accountId: string, slots: Omit<QueueSlot, "id">[]) =>
    api.put<QueueSlot[]>(`${base(accountId)}/queue/slots`, { slots }).then((r) => r.data),

  upcoming: (accountId: string, limit = 20) =>
    api
      .get<QueueState>(`${base(accountId)}/queue/upcoming?limit=${limit}`)
      .then((r) => r.data),

  addToQueue: (accountId: string, postId: string) =>
    api
      .post<{ post_id: string; scheduled_at: string }>(
        `${base(accountId)}/queue/add/${postId}`
      )
      .then((r) => r.data),

  listRecurring: (accountId: string) =>
    api
      .get<{ schedules: RecurringSchedule[] }>(`${base(accountId)}/recurring`)
      .then((r) => r.data.schedules),

  previewRecurring: (accountId: string, body: RecurringInput) =>
    api
      .post<OccurrencePreview>(`${base(accountId)}/recurring/preview`, body)
      .then((r) => r.data),

  createRecurring: (accountId: string, body: RecurringInput) =>
    api.post<RecurringSchedule>(`${base(accountId)}/recurring`, body).then((r) => r.data),

  updateRecurring: (accountId: string, id: string, body: Record<string, unknown>) =>
    api
      .patch<RecurringSchedule>(`${base(accountId)}/recurring/${id}`, body)
      .then((r) => r.data),

  cancelRecurring: (accountId: string, id: string) =>
    api.delete(`${base(accountId)}/recurring/${id}`),
};

export interface RecurringInput {
  template_post_id: string;
  rrule: string;
  /** Naive local: "2026-03-09T10:00:00". Never an ISO string with a Z. */
  starts_at_local: string;
  name?: string | null;
  until_local?: string | null;
  max_occurrences?: number | null;
}

/**
 * A naive local datetime string from a date input and a time input.
 *
 * Deliberately string concatenation rather than `new Date(...)`: routing
 * through a Date object would attach the browser's offset and then strip it,
 * silently shifting the time for anyone whose machine is not in the
 * workspace's zone.
 */
export function localDateTime(date: string, timeOfDay: string): string {
  const time = timeOfDay.length === 5 ? `${timeOfDay}:00` : timeOfDay;
  return `${date}T${time}`;
}

/** Build an RRULE from the simple choices the editor offers. */
export function buildRrule(
  frequency: "daily" | "weekly" | "monthly",
  weekdays: number[]
): string {
  const codes = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
  if (frequency === "weekly" && weekdays.length) {
    const days = [...weekdays].sort((a, b) => a - b).map((d) => codes[d]);
    return `FREQ=WEEKLY;BYDAY=${days.join(",")}`;
  }
  if (frequency === "monthly") return "FREQ=MONTHLY";
  if (frequency === "weekly") return "FREQ=WEEKLY";
  return "FREQ=DAILY";
}

/** Render a server instant in a named zone, for previews. */
export function inZone(iso: string, timeZone: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      timeZone,
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16).replace("T", " ");
  }
}

/**
 * The server's `detail` from a failed request, or a fallback.
 *
 * Typed against `unknown` rather than `any` so the shape has to be narrowed
 * before it is read — the endpoints here return specific, useful messages
 * ("every slot in the next 60 days is taken"), and swallowing them for a
 * generic string would waste the part the user needs.
 */
export function detailFrom(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return fallback;
}
