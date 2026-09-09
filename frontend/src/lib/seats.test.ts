import { describe, expect, it } from "vitest";

import { planLabel, seatSummary } from "./seats";

/** The defect this pins: the team page told a brand-new Free workspace
 *  "1 of 10 team members used · Growth Plan", then refused the very next
 *  invitation with "your Free plan's limit for team members (1)". The 10 and
 *  the "Growth Plan" were hardcoded literals.
 */
describe("seatSummary", () => {
  it("reports the plan's real limit and name", () => {
    const summary = seatSummary({ used: 1, limit: 1, planName: "free" });

    expect(summary.label).toBe("1 of 1 team member used");
    expect(summary.planLabel).toBe("Free plan");
    // The exact situation the walkthrough hit: the meter must agree with the
    // refusal that follows.
    expect(summary.atLimit).toBe(true);
  });

  it("does not claim seats the plan does not have", () => {
    const free = seatSummary({ used: 1, limit: 1, planName: "free" });
    expect(free.label).not.toContain("10");
    expect(free.planLabel).not.toContain("Growth");
  });

  it("counts a plan with room left as not at its limit", () => {
    const summary = seatSummary({ used: 1, limit: 10, planName: "growth" });

    expect(summary.label).toBe("1 of 10 team members used");
    expect(summary.planLabel).toBe("Growth plan");
    expect(summary.atLimit).toBe(false);
    expect(summary.percent).toBe(10);
  });

  it("treats a null limit as unlimited, not as zero seats", () => {
    // How the API expresses an enterprise plan.
    const summary = seatSummary({ used: 42, limit: null, planName: "enterprise" });

    expect(summary.label).toBe("42 team members");
    expect(summary.atLimit).toBe(false);
    // No denominator, so no bar. A bar at 0% or 100% would both be untrue.
    expect(summary.percent).toBeNull();
  });

  it("is at its limit when usage has somehow passed it", () => {
    // Downgrading a plan can leave more members than the new limit allows.
    const summary = seatSummary({ used: 5, limit: 3, planName: "starter" });

    expect(summary.atLimit).toBe(true);
    expect(summary.percent).toBe(100);
  });

  it("says nothing about the plan until settings have loaded", () => {
    // Better a blank than a guess -- guessing is what put "Growth Plan" on a
    // Free workspace.
    expect(seatSummary({ used: 1, limit: null, planName: null }).planLabel).toBeNull();
    expect(planLabel(undefined)).toBeNull();
    expect(planLabel("")).toBeNull();
  });

  it("gets the singular right", () => {
    expect(seatSummary({ used: 1, limit: 1, planName: "free" }).label)
      .toBe("1 of 1 team member used");
    expect(seatSummary({ used: 1, limit: null, planName: "free" }).label)
      .toBe("1 team member");
  });
});
