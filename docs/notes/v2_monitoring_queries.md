"""
V2 ML Model Integration - Monitoring Dashboard Queries
PostgreSQL queries to track V2 routing performance in production
"""

MONITORING_QUERIES = """
================================================================================
V2 ROUTING MONITORING QUERIES
================================================================================

1. ROUTING DISTRIBUTION (Last 24 Hours)
----------------------------------------
-- Shows % of emails in each routing band

SELECT 
    CASE 
        WHEN source = 'v2' AND scam_score < 40 THEN 'v2_auto_clear'
        WHEN source = 'v2' AND scam_score > 85 THEN 'v2_auto_flag'
        WHEN source = 'ai' THEN 'ai_cascade'
        ELSE 'other'
    END as routing_path,
    COUNT(*) as email_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM analyzed_emails
WHERE analyzed_at >= NOW() - INTERVAL '24 hours'
GROUP BY routing_path
ORDER BY email_count DESC;


2. V2 SCORES NEAR AUTO-FLAG THRESHOLD
--------------------------------------
-- CRITICAL: Watch for legitimate emails scoring 0.80-0.90
-- If you see legitimate emails consistently above 0.83, raise threshold to 0.90

SELECT 
    email_id,
    subject,
    sender,
    label_id,
    scam_score,
    ml_confidence as v2_score,
    analyzed_at
FROM analyzed_emails
WHERE source = 'v2'
  AND ml_confidence BETWEEN 0.80 AND 0.95
  AND analyzed_at >= NOW() - INTERVAL '7 days'
ORDER BY ml_confidence DESC
LIMIT 50;


3. FALSE POSITIVES (Legitimate emails auto-flagged by V2)
----------------------------------------------------------
-- Emails V2 auto-flagged (score > 85) but labeled as legitimate

SELECT 
    email_id,
    subject,
    sender,
    scam_score,
    ml_confidence as v2_score,
    scam_indicators,
    analyzed_at
FROM analyzed_emails ae
JOIN email_labels el ON ae.label_id = el.id
WHERE source = 'v2'
  AND scam_score > 85
  AND el.name NOT IN ('Spam', 'Scam', 'Phishing')
  AND analyzed_at >= NOW() - INTERVAL '7 days'
ORDER BY ml_confidence DESC;


4. V2 vs AI DISAGREEMENTS
--------------------------
-- Cases where V2 said high-risk but AI said low-risk (or vice versa)

SELECT 
    email_id,
    subject,
    sender,
    ml_confidence as v2_score,
    scam_score as ai_score,
    label_id,
    provider_used,
    analyzed_at
FROM analyzed_emails
WHERE source = 'ai'
  AND ml_confidence IS NOT NULL
  AND (
    (ml_confidence > 0.70 AND scam_score < 40) OR  -- V2 high, AI low
    (ml_confidence < 0.30 AND scam_score > 60)     -- V2 low, AI high
  )
  AND analyzed_at >= NOW() - INTERVAL '7 days'
ORDER BY ABS(ml_confidence * 100 - scam_score) DESC
LIMIT 20;


5. PERFORMANCE METRICS
----------------------
-- AI cascade load reduction achieved by V2

WITH routing_stats AS (
    SELECT 
        COUNT(*) as total_emails,
        SUM(CASE WHEN source = 'v2' THEN 1 ELSE 0 END) as v2_handled,
        SUM(CASE WHEN source = 'ai' THEN 1 ELSE 0 END) as ai_handled,
        SUM(CASE WHEN provider_used IS NOT NULL THEN 1 ELSE 0 END) as ai_api_calls
    FROM analyzed_emails
    WHERE analyzed_at >= NOW() - INTERVAL '24 hours'
)
SELECT 
    total_emails,
    v2_handled,
    ai_handled,
    ROUND(v2_handled * 100.0 / total_emails, 2) as v2_percentage,
    ROUND(ai_handled * 100.0 / total_emails, 2) as ai_percentage,
    total_emails - ai_api_calls as api_calls_saved
FROM routing_stats;


6. DAILY ROUTING TREND (Last 7 Days)
-------------------------------------
-- Track how routing distribution changes over time

SELECT 
    DATE(analyzed_at) as date,
    COUNT(*) as total,
    SUM(CASE WHEN source = 'v2' AND scam_score < 40 THEN 1 ELSE 0 END) as auto_clear,
    SUM(CASE WHEN source = 'ai' THEN 1 ELSE 0 END) as ai_cascade,
    SUM(CASE WHEN source = 'v2' AND scam_score > 85 THEN 1 ELSE 0 END) as auto_flag
FROM analyzed_emails
WHERE analyzed_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(analyzed_at)
ORDER BY date DESC;


7. THRESHOLD ADJUSTMENT RECOMMENDATION
---------------------------------------
-- Suggests new auto-flag threshold based on max legitimate score

WITH legit_scores AS (
    SELECT MAX(ml_confidence) as max_legit_score
    FROM analyzed_emails ae
    JOIN email_labels el ON ae.label_id = el.id
    WHERE source = 'v2'
      AND el.name NOT IN ('Spam', 'Scam', 'Phishing')
      AND analyzed_at >= NOW() - INTERVAL '7 days'
)
SELECT 
    max_legit_score,
    ROUND(max_legit_score + 0.05, 2) as suggested_threshold,
    CASE 
        WHEN max_legit_score > 0.85 THEN 'RAISE THRESHOLD to 0.90'
        WHEN max_legit_score > 0.80 THEN 'MONITOR CLOSELY'
        ELSE 'THRESHOLD OK'
    END as recommendation
FROM legit_scores;

================================================================================
ALERT CONDITIONS
================================================================================

Set up alerts for:

1. False positive rate > 2% in auto-flag band
   → Raise auto-flag threshold immediately

2. Legitimate emails scoring > 0.85
   → Review and adjust threshold to max_legit + 0.05

3. AI cascade load > 95%
   → V2 might be down or thresholds too conservative

4. V2 vs AI disagreement rate > 15%
   → Indicates model drift, may need retraining

================================================================================
GRAFANA/MONITORING DASHBOARD
================================================================================

Recommended metrics to graph:

1. Routing band distribution (pie chart, 24h rolling)
2. V2 score distribution histogram (separate for legit/phishing)
3. AI cascade load over time (line chart)
4. False positive rate (auto-flag band, daily)
5. V2 vs AI disagreement rate (weekly)
"""

if __name__ == "__main__":
    print(MONITORING_QUERIES)
