# Walkthrough defect log

Filled in as the walkthrough runs. **Nothing here gets fixed during the walk** —
log it, move on, triage at the end.

Severity:
- **S1** blocks a user completely, or loses/corrupts data
- **S2** a core path works but is wrong, or needs a workaround a user would not find
- **S3** confusing, ugly, or slow, but completable
- **S4** polish

| # | Step | Severity | What happened | Expected | Notes |
|---|------|----------|---------------|----------|-------|
| ~~1~~ **FIXED** | 6 (schedule) | S2 | The composer's manual schedule builds `new Date("2026-03-09T10:00")`, which parses in the **browser's** timezone, then sends `.toISOString()`. An agency in London scheduling for a Sydney workspace sets a time eleven hours out, and the error changes by an hour when either side's clocks move. | The time entered should mean that time on the *workspace's* clock, as it does for queue slots and recurring schedules. | Found while building scope §9's remainder, not by the walkthrough. "Add to queue" and "Repeat" avoid it — the server resolves those. Fixed: `/schedule` now takes `scheduled_at_local` (a workspace wall-clock reading) or `scheduled_at` (an instant that must carry an offset); a naive `scheduled_at` is refused rather than assumed UTC. The read path was wrong the same way — a post set for 10:00 Sydney rendered as 23:00 to a London viewer, and saving that form wrote 23:00 Sydney — so both directions were fixed. `tests/test_post_contract.py`. |

## Observations that are not defects

Things worth remembering that are not bugs — friction, missing features, ideas
for Phase 2 ordering.

- ~~`POST /posts/` takes `target_account_ids`, but the response returns
  `target_accounts`.~~ **Fixed.** Post writes now refuse unknown fields with a
  422 naming the key, and accept `target_accounts` as an alias so
  read-modify-write works against the API's own response.
