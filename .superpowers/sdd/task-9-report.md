## Review finding fix: fresh active draft guard

**Finding:** Missing test for the branch where an active `needs_review` draft has `created_at` after the latest customer message — `sync_once` should skip draft generation.

**Fix:** Added `test_sync_keeps_active_draft_when_still_fresh` in `tests/test_ingest.py`.

**Scenario:**
- Pre-seeded `needs_review` draft at `2026-08-06T10:01:00+00:00`
- Latest customer message at `2026-08-06T10:00:00+00:00` (older than draft)
- `sync_once` creates 0 new drafts, draft count stays 1, `drafts_created == 0`
- `generate_draft` is not invoked (AssertionError guard)

**Tests:** `pytest tests/test_ingest.py` — 3 passed; full suite — 23 passed.
