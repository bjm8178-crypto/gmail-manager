# Latest Email Prioritization Fix

## Problem
The current system uses cursor-based pagination (`get_scan_cursor` / `save_scan_cursor`) that progresses chronologically through Gmail. When there are new emails, the system continues from where it left off in the old emails instead of fetching the latest ones first.

## Root Cause
1. `analyze_bulk_ordered()` line 808: `cursor = get_scan_cursor(user_id)`
2. `fetch_only_pipeline()` line 1168: `cursor = get_scan_cursor(user_id)`
3. Both functions pass this cursor to `fetch_emails()`, which continues from the old position

## Solution
**Always start from the beginning (latest emails) by passing `page_token=None` to `fetch_emails()`:**
- Remove cursor loading before fetch
- Remove cursor saving after fetch
- The Gmail API by default returns emails in reverse chronological order (newest first)
- Deduplication via `is_already_analyzed()` prevents reprocessing

## Changes Required
1. **`analyze_bulk_ordered()`**: Remove lines 808, 828-829 (cursor load/save)
2. **`fetch_only_pipeline()`**: Remove lines 1168, 1178-1179 (cursor load/save)
3. Pass `page_token=None` explicitly to `fetch_emails()` in both functions

## Verification
- Run analysis multiple times
- Confirm the system fetches the same latest N emails each time
- New emails should appear immediately in the next analysis run
