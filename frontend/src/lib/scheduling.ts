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

/**
 * A stored instant, split into the date and time inputs a form needs, as read
 * on a *named* clock rather than the browser's.
 *
 * The counterpart to `localDateTime`. Reading a scheduled post back with
 * `new Date(iso).getHours()` renders it in whatever timezone the viewer's
 * machine is in, so a post set for 10:00 Sydney shows as 23:00 the previous
 * day to someone in London — and saving that form back would store 23:00
 * Sydney. Getting the write path right is only half the fix.
 */
export function wallClockIn(
  iso: string,
  timeZone: string
): { date: string; time: string } {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(new Date(iso));

    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
    // Intl renders midnight as "24" in some engines; the inputs need "00".
    const hour = get("hour") === "24" ? "00" : get("hour");
    return {
      date: `${get("year")}-${get("month")}-${get("day")}`,
      time: `${hour}:${get("minute")}`,
    };
  } catch {
    // An unusable zone must not blank the form. Fall back to the raw reading,
    // which is at least the value the server holds.
    return { date: iso.slice(0, 10), time: iso.slice(11, 16) };
  }
}

/** The date and time the schedule fields should start on, an hour ahead.
 *
 *  On the **workspace's** clock, which is what the note under those fields
 *  promises: "Times are on the workspace's clock, not your computer's."
 *
 *  They used to be built with `new Date()` and `getHours()`, so the default was
 *  the browser's wall clock presented as the workspace's. On an IST machine
 *  scheduling into a UTC workspace the fields opened on 03:54 while it was
 *  21:24 in the workspace -- six and a half hours out, in the one place the
 *  user is most likely to accept what is offered. Defect #1 fixed how these
 *  fields are parsed and rendered; nobody looked at what they were seeded with.
 *
 *  An hour's lead is kept from the old behaviour: far enough ahead that the
 *  time has not passed by the time the form is submitted.
 */
export function defaultScheduleFields(
  timeZone: string,
  now: Date = new Date()
): { date: string; time: string } {
  const anHourFromNow = new Date(now.getTime() + 60 * 60 * 1000);
  return wallClockIn(anHourFromNow.toISOString(), timeZone);
}
