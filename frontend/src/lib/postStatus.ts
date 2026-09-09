/** What a post's status means, in one place.
 *
 *  The calendar used to narrow the backend's twelve statuses down to five with
 *  a `mapStatus` that fell through to `"draft"` for anything it did not
 *  recognise. Two of those five were wrong in ways a user could act on:
 *
 *  * `approved`, `in_review` and `changes_requested` all rendered as **Draft**.
 *    A post an approver had signed off sat in the Drafts filter looking
 *    untouched, and the `status === "draft"` action gate opened for it.
 *  * `partially_published` mapped to `published`, so a post that **failed on
 *    one of its two platforms** got a green "Published" pill and was counted
 *    among the successes. The panel below it showed the failure in red at the
 *    same time.
 *
 *  Nothing was missing from the type: `ReviewStatus` already lists all twelve.
 *  The mapping simply threw information away, so this module does not add a
 *  vocabulary -- it stops discarding the one that was there.
 */

import type { ReviewStatus } from "@/lib/review";

/** Every status the backend's `PostStatus` enum can emit, in its order.
 *
 *  Mirrored deliberately rather than derived: the API sends strings, and this
 *  list is what the UI promises to understand. `test_frontend_knows_every_post_status`
 *  in the backend suite fails if the enum and this list drift apart, which is
 *  the only way a new status can reach a UI that silently calls it a draft.
 */
export const POST_STATUSES = [
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
] as const satisfies readonly ReviewStatus[];

const KNOWN = new Set<string>(POST_STATUSES);

/** The backend's status string, unchanged when we understand it.
 *
 *  An unrecognised status still falls back to `"draft"` -- something has to be
 *  rendered -- but it warns, because silently doing that is what this module
 *  exists to stop.
 */
export function mapStatus(backendStatus: string | null | undefined): ReviewStatus {
  const status = (backendStatus ?? "").toLowerCase();
  if (KNOWN.has(status)) return status as ReviewStatus;
  if (status) {
    console.warn(
      `Unknown post status "${status}"; showing it as a draft. ` +
        "Add it to POST_STATUSES.",
    );
  }
  return "draft";
}

/** The buckets the calendar counts and filters by.
 *
 *  `published` holds only fully published posts. A partial publish gets its own
 *  bucket rather than being folded into either success or failure: it is
 *  genuinely both, and the whole point is that a user can see it happened.
 */
export const STATUS_BUCKETS = {
  published: ["published"],
  partially_published: ["partially_published"],
  scheduled: ["scheduled", "publishing"],
  in_review: [
    "pending_approval",
    "in_review",
    "client_review",
    "changes_requested",
    "approved",
  ],
  draft: ["draft", "preview"],
  failed: ["failed"],
} as const satisfies Record<string, readonly ReviewStatus[]>;

export type StatusBucket = keyof typeof STATUS_BUCKETS;

const BUCKET_OF = new Map<ReviewStatus, StatusBucket>(
  (Object.entries(STATUS_BUCKETS) as [StatusBucket, readonly ReviewStatus[]][])
    .flatMap(([bucket, statuses]) => statuses.map((s) => [s, bucket] as const)),
);

export function bucketOf(status: ReviewStatus): StatusBucket {
  return BUCKET_OF.get(status) ?? "draft";
}

export function inBucket(status: ReviewStatus, bucket: StatusBucket): boolean {
  return bucketOf(status) === bucket;
}

/** Whether a post is finished going out to every target it was given.
 *
 *  Deliberately false for `partially_published`. A partial publish is not a
 *  publish, and the places that ask this question -- the green pill, the
 *  success counter -- are exactly the ones that were lying.
 */
export function isFullyPublished(status: ReviewStatus): boolean {
  return status === "published";
}

/** Whether a post is still being worked on and can be freely edited.
 *
 *  `approved` is not a draft: someone signed it off, and offering the draft
 *  actions for it invites quietly editing approved copy.
 */
export function isEditableDraft(status: ReviewStatus): boolean {
  return inBucket(status, "draft");
}
