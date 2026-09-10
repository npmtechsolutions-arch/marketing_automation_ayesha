/**
 * The competitor logic that is a rule rather than markup.
 *
 * `followerChange` is the one place this feature could quietly invent a fact:
 * it turns two measurements into a claim about growth, and every case where it
 * *cannot* honestly do that has to come back null rather than 0. "0 followers
 * gained" and "we have not measured twice yet" are different sentences, and
 * only one of them is ever true here.
 */
import { describe, expect, it } from "vitest";
import {
  coveredRange, followerChange, type CompetitorSnapshot,
} from "./competitors";

const snap = (date: string, followers: number | null): CompetitorSnapshot => ({
  date,
  followers,
  media_count: null,
});

describe("followerChange", () => {
  it("reports growth between the first and last measurement", () => {
    const change = followerChange([
      snap("2026-09-01", 12000),
      snap("2026-09-08", 12400),
    ]);
    expect(change).toEqual({ absolute: 400, percent: 3.3 });
  });

  it("reports a loss as a negative", () => {
    const change = followerChange([
      snap("2026-09-01", 12000),
      snap("2026-09-08", 11400),
    ]);
    expect(change?.absolute).toBe(-600);
  });

  it("is null with only one measurement", () => {
    // One snapshot is a fact, not a trend. Reporting +0 would say they did not
    // grow, when the truth is that we have only looked once.
    expect(followerChange([snap("2026-09-01", 12000)])).toBeNull();
  });

  it("is null when the only points we hold are unmeasured", () => {
    // A private account yields nulls; two of them are not two measurements.
    expect(
      followerChange([snap("2026-09-01", null), snap("2026-09-08", null)])
    ).toBeNull();
  });

  it("skips unmeasured weeks rather than treating them as zero", () => {
    const change = followerChange([
      snap("2026-09-01", 12000),
      snap("2026-09-08", null),
      snap("2026-09-15", 12500),
    ]);
    // The gap week is absent from the arithmetic, not a dive to zero and back.
    expect(change).toEqual({ absolute: 500, percent: 4.2 });
  });

  it("has no percentage when the account started at zero", () => {
    // A rate with no denominator is null, not 0% -- the same rule the reports
    // follow for engagement.
    const change = followerChange([snap("2026-09-01", 0), snap("2026-09-08", 40)]);
    expect(change?.absolute).toBe(40);
    expect(change?.percent).toBeNull();
  });
});

describe("coveredRange", () => {
  it("is null below two points, so no caption claims a window", () => {
    expect(coveredRange([snap("2026-09-01", 1)])).toBeNull();
  });

  it("names the span the chart actually covers", () => {
    expect(coveredRange([snap("2026-09-01", 1), snap("2026-09-08", 2)])).toContain(
      "–"
    );
  });
});
