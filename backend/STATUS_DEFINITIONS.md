# Status Field Definitions (Phase 4)

Last updated: 2026-10-14

## analysis_status

Three-state field tracking overall email analysis completion.

### States

**`completed`** — Risk score AND label both obtained successfully
- Valid scam_score (0-100 integer)
- Valid label (matched against user's Gmail labels, or "Unknown" as explicit fallback)
- Independent of ML model availability (AI-only is still `completed` if score + label exist)
- Independent of URL scan results (Phase 3 Task 11: URL scan failures isolated to url_scan_status)

**`partial`** — Risk score obtained but label missing/unusable
- Valid scam_score exists
- label_id is NULL (label could not be resolved to a real Gmail label)
- This happens when:
  - AI/ML returned invalid label AND fuzzy match failed AND label_only retry failed
  - Label was "Unknown" but no Gmail label with that exact name exists

**`failed`** — No risk score obtained (analysis pipeline crashed)
- scam_score is NULL
- Exception occurred before any valid score could be produced
- Email remains in failed state until manual retry or auto-repair

### Key Rules (Phase 4 Task 12)

1. ML model availability does NOT affect status:
   - AI-only path (no ML) → `completed` if score + label exist
   - V2 path with ML → `completed` if score + label exist
   - Both are equally "complete" from status perspective

2. URL scan results do NOT affect analysis_status (Phase 3 Task 11):
   - url_scan_status can be 'partial', 'unavailable', or 'threat_detected'
   - analysis_status remains `completed` as long as score + label exist
   - URL threats are reflected in the scam_score (boosted to ≥95) and indicators

3. Status resolution order:
   ```
   if scam_score is NULL:
       analysis_status = 'failed'
   elif label_id is NULL:
       analysis_status = 'partial'
   else:
       analysis_status = 'completed'
   ```

## category_status

Two-state field tracking label categorization.

### States

**`completed`** — Label successfully matched to a Gmail label
- label field contains a valid label name
- label_id field contains the corresponding Gmail label ID

**`unavailable`** — Label resolution failed
- label is "Unknown"
- label_id is NULL
- Occurs when AI returned invalid label and all retry/match attempts failed

## url_scan_status

Four-state field tracking URL security scanning (independent of analysis_status per Phase 3 Task 11).

### States

**`completed`** — All extracted URLs successfully scanned, no threats found

**`partial`** — Some URLs scanned but scan was incomplete:
- More URLs extracted than MAX_URLS_SCANNED cap (30)
- Some URL scans failed (timeout, API error, etc.) but at least one succeeded

**`unavailable`** — URL scanning unavailable or entirely failed:
- Safe Browsing API key not configured
- All URL scan attempts failed
- No URLs were successfully checked

**`threat_detected`** — At least one URL confirmed as malicious by Safe Browsing API
- Takes precedence over other states
- scam_score automatically boosted to ≥95
- "Known malicious link detected" added to scam_indicators

**`not_applicable`** — No URLs found in email body

## Frontend Badge Mapping

Current frontend displays analysis_status as a badge. Phase 4 clarification:

- `completed` → Green "Complete" badge (score + label exist)
- `partial` → Yellow "Partial" badge (score exists, label missing)
- `failed` → Red "Failed" badge (no score)
- `pending` → Gray "Pending" badge (not yet analyzed)

**No changes needed** — Frontend already correctly interprets these states.

## Auto-Repair Eligibility (Phase 4 Task 13)

Emails eligible for auto-repair at end of bulk run:
- `analysis_status = 'failed'` (no score obtained)
- `analysis_status = 'partial'` (score exists but label missing)
- `label = 'Unknown'` (explicit catch-all fallback)

Auto-repair attempts up to 2 retries with exponential backoff (5s, 15s) within the same bulk job, NOT counted against hourly rate limit.

## Backfill Scenario (Phase 4 Task 14)

Emails marked `analysis_status = 'partial'` under old logic that would be `completed` under new Phase 4 definition:
- Old logic: `url_scan_unavailable=True` → forced `partial`
- New logic: URL scan failures isolated, `completed` if score + label exist

Backfill script will recompute status for these rows without re-running AI analysis.
