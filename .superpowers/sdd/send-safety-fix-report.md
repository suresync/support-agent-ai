# Send-safety fix report

- Prevented approvals unless a draft is currently awaiting review.
- Added an atomic, committed `needs_review` to `sending` claim before live sends.
- Restored failed sends to `needs_review` with the send error recorded.
- Added reject/regenerate audit entries and paginated seven-day syncs in batches of 50.
- Added regression coverage for repeat approvals, send failures, auditing, and pagination.
