-- Phase 4 Task 14: Backfill script to recompute analysis_status for existing rows
-- DO NOT RUN without explicit approval — this modifies production data
--
-- Context: Before Phase 4, analysis_status was set to 'partial' when:
--   - url_scan_unavailable = true (URL scan failed)
--   - label_id is NULL (label resolution failed)
--   - AI/ML returned analysis_status='partial'
--
-- After Phase 4 Task 12, analysis_status should be:
--   - 'completed' iff scam_score exists AND label_id exists
--   - 'partial' only when scam_score exists but label_id is NULL
--   - 'failed' only when scam_score is NULL
--
-- This backfill identifies rows that are currently 'partial' but should be 'completed'
-- under the new definition (have both scam_score AND label_id).

-- Step 1: Preview affected rows (run this first to see what will change)
SELECT 
    email_id,
    sender,
    subject,
    scam_score,
    label,
    label_id,
    analysis_status AS current_status,
    CASE
        WHEN scam_score IS NULL THEN 'failed'
        WHEN label_id IS NULL THEN 'partial'
        ELSE 'completed'
    END AS new_status,
    url_scan_status,
    received_at
FROM emails
WHERE analysis_status = 'partial'
  AND scam_score IS NOT NULL
  AND label_id IS NOT NULL
ORDER BY received_at DESC
LIMIT 100;

-- Step 2: Count total affected rows
SELECT 
    COUNT(*) AS total_to_update,
    COUNT(DISTINCT user_id) AS affected_users
FROM emails
WHERE analysis_status = 'partial'
  AND scam_score IS NOT NULL
  AND label_id IS NOT NULL;

-- Step 3: Breakdown by reason (why they were marked partial before Phase 4)
SELECT 
    CASE
        WHEN label = 'Unknown' THEN 'Unknown label (but label_id exists)'
        WHEN url_scan_status IN ('partial', 'unavailable') THEN 'URL scan incomplete'
        ELSE 'Other reason'
    END AS reason,
    COUNT(*) AS count
FROM emails
WHERE analysis_status = 'partial'
  AND scam_score IS NOT NULL
  AND label_id IS NOT NULL
GROUP BY reason
ORDER BY count DESC;

-- Step 4: THE ACTUAL UPDATE (only run after reviewing Steps 1-3)
-- COMMENTED OUT FOR SAFETY — uncomment and run only with explicit approval

/*
BEGIN;

-- Update analysis_status to 'completed' for rows that have both score and label
UPDATE emails
SET analysis_status = 'completed'
WHERE analysis_status = 'partial'
  AND scam_score IS NOT NULL
  AND label_id IS NOT NULL;

-- Verify update
SELECT 
    COUNT(*) AS updated_count,
    MIN(received_at) AS earliest,
    MAX(received_at) AS latest
FROM emails
WHERE analysis_status = 'completed'
  AND label_id IS NOT NULL
  AND scam_score IS NOT NULL
  AND received_at >= (
      SELECT MIN(received_at) 
      FROM emails 
      WHERE analysis_status = 'partial'
        AND scam_score IS NOT NULL
        AND label_id IS NOT NULL
  );

-- If the counts look correct, commit. Otherwise:
-- ROLLBACK;

COMMIT;
*/

-- Step 5: Post-backfill verification
-- Run this after Step 4 completes to verify correctness
SELECT 
    analysis_status,
    COUNT(*) AS count,
    COUNT(CASE WHEN scam_score IS NULL THEN 1 END) AS null_score_count,
    COUNT(CASE WHEN label_id IS NULL THEN 1 END) AS null_label_count
FROM emails
GROUP BY analysis_status
ORDER BY 
    CASE analysis_status
        WHEN 'completed' THEN 1
        WHEN 'partial' THEN 2
        WHEN 'failed' THEN 3
        WHEN 'pending' THEN 4
        ELSE 5
    END;

-- Step 6: Check for any remaining inconsistencies
-- These should be zero rows if Phase 4 logic is correct
SELECT 
    'Completed but missing score' AS issue,
    COUNT(*) AS count
FROM emails
WHERE analysis_status = 'completed' AND scam_score IS NULL

UNION ALL

SELECT 
    'Completed but missing label' AS issue,
    COUNT(*) AS count
FROM emails
WHERE analysis_status = 'completed' AND label_id IS NULL

UNION ALL

SELECT 
    'Partial but has both score and label' AS issue,
    COUNT(*) AS count
FROM emails
WHERE analysis_status = 'partial' AND scam_score IS NOT NULL AND label_id IS NOT NULL

UNION ALL

SELECT 
    'Failed but has score' AS issue,
    COUNT(*) AS count
FROM emails
WHERE analysis_status = 'failed' AND scam_score IS NOT NULL;
