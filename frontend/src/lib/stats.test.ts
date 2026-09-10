/**
 * The two Walk B dashboard defects, pinned.
 *
 * A workspace that has measured nothing must not be told it is up, and must
 * not be shown zeroes it never earned.
 */
import { describe, expect, it } from "vitest";
import { changeBadge, metricText, rateText } from "./stats";

describe("changeBadge", () => {
  it("is null when there is no comparison", () => {
    // The exact defect: the old guard was `change !== undefined`, so null fell
    // through and `null >= 0` rendered a green "+%" with no number in it.
    expect(changeBadge(null)).toBeNull();
    expect(changeBadge(undefined)).toBeNull();
  });

  it("is null for a non-finite number rather than printing NaN%", () => {
    expect(changeBadge(NaN)).toBeNull();
    expect(changeBadge(Infinity)).toBeNull();
  });

  it("signs a rise and marks it positive", () => {
    expect(changeBadge(12.5)).toEqual({ text: "+12.5%", positive: true });
  });

  it("keeps a fall negative and does not add a plus", () => {
    expect(changeBadge(-4)).toEqual({ text: "-4%", positive: false });
  });

  it("treats no change as flat-but-present, not absent", () => {
    // A measured 0% change is a real answer and must still render.
    expect(changeBadge(0)).toEqual({ text: "+0%", positive: true });
  });
});

describe("metricText", () => {
  it("renders an em dash where nothing was measured", () => {
    expect(metricText(null)).toBe("—");
    expect(metricText(undefined)).toBe("—");
  });

  it("keeps a real zero, which is a measurement", () => {
    expect(metricText(0)).toBe("0");
  });

  it("uses the formatter when one is given", () => {
    expect(metricText(61233, (n) => n.toLocaleString("en-US"))).toBe("61,233");
  });
});

describe("rateText", () => {
  it("is an em dash with no denominator", () => {
    // 0% engagement against unmeasured interactions reads as "your content is
    // failing" when the truth is "we cannot measure this".
    expect(rateText(null)).toBe("—");
  });

  it("keeps a measured zero rate", () => {
    expect(rateText(0)).toBe("0.00%");
  });

  it("converts a 0-1 rate to a percentage", () => {
    expect(rateText(0.0432)).toBe("4.32%");
  });
});
