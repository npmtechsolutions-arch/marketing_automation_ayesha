import { describe, expect, it } from "vitest";

import { defaultScheduleFields, wallClockDate, wallClockIn } from "./scheduling";

/** The composer's schedule fields say, directly beneath them:
 *
 *    "Times are on the workspace's clock, not your computer's."
 *
 *  These pin that the value they *open on* obeys it too. It did not: the
 *  defaults were built from `new Date()` and `getHours()`, so on an IST machine
 *  scheduling into a UTC workspace the fields offered 03:54 while the workspace
 *  clock read 21:24 -- and the most likely thing a user does with a prefilled
 *  time is accept it.
 */
describe("defaultScheduleFields", () => {
  // 21:24 UTC on 8 September 2026.
  const now = new Date("2026-09-08T21:24:00Z");

  it("is an hour ahead on the workspace clock, not the browser's", () => {
    expect(defaultScheduleFields("UTC", now)).toEqual({
      date: "2026-09-08",
      time: "22:24",
    });
  });

  it("gives a different wall-clock reading per workspace, from one instant", () => {
    const utc = defaultScheduleFields("UTC", now);
    const sydney = defaultScheduleFields("Australia/Sydney", now);
    const la = defaultScheduleFields("America/Los_Angeles", now);

    expect(utc.time).toBe("22:24");
    // 22:24 UTC on the 8th is 08:24 on the 9th in Sydney (UTC+10).
    expect(sydney).toEqual({ date: "2026-09-09", time: "08:24" });
    // ...and 15:24 on the 8th in Los Angeles (UTC-7 in September).
    expect(la).toEqual({ date: "2026-09-08", time: "15:24" });
  });

  it("rolls the date over when the hour crosses midnight there", () => {
    // 23:30 UTC is already the next day in Sydney.
    const late = new Date("2026-09-08T23:30:00Z");
    expect(defaultScheduleFields("Australia/Sydney", late).date).toBe("2026-09-09");
  });

  it("agrees with how the same instant is rendered back", () => {
    // The seed and the read-back path must not disagree, or a user who accepts
    // the default sees it change the moment the post is saved.
    const anHourOn = new Date(now.getTime() + 3600_000).toISOString();
    for (const zone of ["UTC", "Australia/Sydney", "America/Los_Angeles", "Asia/Kolkata"]) {
      expect(defaultScheduleFields(zone, now)).toEqual(wallClockIn(anHourOn, zone));
    }
  });

  it("handles a half-hour offset", () => {
    // India is UTC+5:30, which is where the original defect was observed.
    expect(defaultScheduleFields("Asia/Kolkata", now)).toEqual({
      date: "2026-09-09",
      time: "03:54",
    });
  });

  it("falls back rather than throwing on an unusable timezone", () => {
    // workspace_timezone() on the server falls back to UTC for an unknown
    // name; the form must still open on something.
    const result = defaultScheduleFields("Not/AZone", now);
    expect(result.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.time).toMatch(/^\d{2}:\d{2}$/);
  });
});

describe("wallClockDate", () => {
  // 21:29 UTC on 9 September 2026 -- the exact instant from the walkthrough.
  const published = "2026-09-09T21:29:00Z";

  it("reads the workspace's wall clock in the fields the calendar uses", () => {
    const d = wallClockDate(published, "UTC");

    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(8); // September
    expect(d.getDate()).toBe(9);
    expect(d.getHours()).toBe(21);
    expect(d.getMinutes()).toBe(29);
  });

  it("puts a post on the workspace's day, not the viewer's", () => {
    // The defect: on an IST machine this instant read as 02:59 on the 10th, so
    // the post sat in the wrong day cell as well as showing the wrong time.
    const utc = wallClockDate(published, "UTC");
    const sydney = wallClockDate(published, "Australia/Sydney");

    expect(utc.getDate()).toBe(9);
    // 21:29 UTC is already 07:29 the next morning in Sydney -- genuinely a
    // different day *for that workspace*, which is the point.
    expect(sydney.getDate()).toBe(10);
    expect(sydney.getHours()).toBe(7);
  });

  it("is the same reading the composer would show for that instant", () => {
    for (const zone of ["UTC", "Australia/Sydney", "America/Los_Angeles"]) {
      const d = wallClockDate(published, zone);
      const { date, time } = wallClockIn(published, zone);
      const pad = (n: number) => String(n).padStart(2, "0");
      expect(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`).toBe(date);
      expect(`${pad(d.getHours())}:${pad(d.getMinutes())}`).toBe(time);
    }
  });
});
