import { describe, expect, it, vi } from "vitest";

import {
  POST_STATUSES,
  STATUS_BUCKETS,
  bucketOf,
  isEditableDraft,
  isFullyPublished,
  mapStatus,
} from "./postStatus";

/** The statuses the backend's PostStatus enum can emit.
 *
 *  Written out rather than imported, so this file states the contract the UI
 *  is promising to honour. The backend's own
 *  `test_frontend_knows_every_post_status` asserts the enum still matches it,
 *  so the two cannot drift without something going red.
 */
const BACKEND_STATUSES = [
  "draft",
  "preview",
  "pending_approval",
  "in_review",
  "changes_requested",
  "client_review",
  "approved",
  "scheduled",
  "publishing",
  "published",
  "partially_published",
  "failed",
];

describe("mapStatus", () => {
  it("knows every status the backend can send", () => {
    expect([...POST_STATUSES].sort()).toEqual([...BACKEND_STATUSES].sort());
  });

  it.each(BACKEND_STATUSES)("passes %s through unchanged", (status) => {
    expect(mapStatus(status)).toBe(status);
  });

  it("does not quietly relabel review states as drafts", () => {
    // The defect: approved, in_review and changes_requested all fell through
    // to "draft", so a post an approver had signed off looked untouched.
    for (const status of ["approved", "in_review", "changes_requested", "client_review"]) {
      expect(mapStatus(status)).not.toBe("draft");
    }
  });

  it("does not report a partial publish as a publish", () => {
    // The defect: partially_published mapped to published, so a post that
    // failed on one of two platforms got a green pill and a success count.
    expect(mapStatus("partially_published")).toBe("partially_published");
    expect(isFullyPublished("partially_published")).toBe(false);
    expect(isFullyPublished("published")).toBe(true);
  });

  it("is case-insensitive, because the API has sent both", () => {
    expect(mapStatus("PUBLISHED")).toBe("published");
  });

  it("falls back to draft for an unknown status, but says so", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(mapStatus("teleported")).toBe("draft");
    expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });

  it("treats a missing status as a draft without warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(mapStatus(undefined)).toBe("draft");
    expect(mapStatus(null)).toBe("draft");
    expect(mapStatus("")).toBe("draft");
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("buckets", () => {
  it("puts every status in exactly one bucket", () => {
    const placed = Object.values(STATUS_BUCKETS).flat();
    expect([...placed].sort()).toEqual([...BACKEND_STATUSES].sort());
    expect(new Set(placed).size).toBe(placed.length);
  });

  it("keeps a partial publish out of both success and failure", () => {
    expect(bucketOf("partially_published")).toBe("partially_published");
    expect(STATUS_BUCKETS.published).not.toContain("partially_published");
    expect(STATUS_BUCKETS.failed).not.toContain("partially_published");
  });

  it("keeps review states out of the drafts bucket", () => {
    for (const status of ["pending_approval", "in_review", "client_review",
                          "changes_requested", "approved"] as const) {
      expect(bucketOf(status)).toBe("in_review");
      expect(isEditableDraft(status)).toBe(false);
    }
  });

  it("counts a post being published as scheduled rather than done", () => {
    expect(bucketOf("publishing")).toBe("scheduled");
    expect(isFullyPublished("publishing")).toBe(false);
  });

  it("still treats real drafts as editable", () => {
    expect(isEditableDraft("draft")).toBe(true);
    expect(isEditableDraft("preview")).toBe(true);
  });
});
