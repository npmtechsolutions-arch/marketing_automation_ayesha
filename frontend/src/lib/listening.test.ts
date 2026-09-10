/**
 * The one piece of listening logic that is a rule rather than markup: what a
 * polling interval costs.
 *
 * It lives in `src/lib` and is pinned here because it is the number someone
 * reads before deciding to poll six times as often, and a component that
 * computed it inline would be a place for it to be quietly wrong.
 */
import { describe, expect, it } from "vitest";
import { dailyCeilingUsd, neverRan, type ListeningQuery } from "./listening";

const READ_COST = 0.005;
const MAX_RESULTS = 25;

describe("dailyCeilingUsd", () => {
  it("prices one query at six-hourly polling", () => {
    // 4 polls x 25 posts x $0.005
    expect(dailyCeilingUsd(1, 6, MAX_RESULTS, READ_COST)).toBe(0.5);
  });

  it("scales with the number of active queries", () => {
    expect(dailyCeilingUsd(3, 6, MAX_RESULTS, READ_COST)).toBe(1.5);
  });

  it("shows hourly polling as six times the cost of six-hourly", () => {
    // The whole point of showing the number next to the interval control.
    const sixHourly = dailyCeilingUsd(1, 6, MAX_RESULTS, READ_COST);
    const hourly = dailyCeilingUsd(1, 1, MAX_RESULTS, READ_COST);
    expect(hourly).toBe(sixHourly * 6);
  });

  it("is zero with nothing being watched", () => {
    expect(dailyCeilingUsd(0, 6, MAX_RESULTS, READ_COST)).toBe(0);
  });
});

describe("neverRan", () => {
  const query = {
    id: "1", platform: "twitter", query_text: "brand", is_active: true,
    created_at: null, last_polled_at: null, last_success_at: null,
    next_poll_at: null, last_error: null, last_error_at: null, healthy: true,
    requests_made: 0, posts_read: 0, estimated_cost_usd: 0,
  } satisfies ListeningQuery;

  it("is true for a query that has never succeeded", () => {
    expect(neverRan(query)).toBe(true);
  });

  it("is false once one poll has landed", () => {
    // A search that failed *after* succeeding has still run: its stream is
    // stale, not empty, and the two deserve different words.
    expect(neverRan({ ...query, last_success_at: "2026-09-10T00:00:00Z" })).toBe(
      false
    );
  });
});
