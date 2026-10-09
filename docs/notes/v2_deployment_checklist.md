"""
V2 Integration - Complete Deployment Checklist
Everything needed to deploy V2 routing to production
"""

DEPLOYMENT_CHECKLIST = """
================================================================================
V2 ML MODEL DEPLOYMENT CHECKLIST
================================================================================

## PRE-DEPLOYMENT

### 1. Environment Variables
Add to .env file:

```bash
# V2 ML Model Confidence-Band Routing
V2_AUTO_CLEAR_THRESHOLD=0.40
V2_AUTO_FLAG_THRESHOLD=0.85
```

### 2. Verify Model Files
```bash
cd backend/
ls -lh scam_classifier_v2.pkl    # Should be ~12.5 MB
ls -lh model_metadata_v2.json    # Should exist
python -c "import joblib; joblib.load('scam_classifier_v2.pkl'); print('✓ Model loads')"
```

### 3. Verify Dependencies
```bash
python -c "from predict import predict_email; print('✓ predict.py works')"
python -c "from v2_routing import route_email_with_v2; print('✓ v2_routing.py works')"
```

### 4. Test V2 Module Standalone
```bash
python test_short_informal_emails.py
# Should show 3/18 correct (before threshold adjustment to 0.85)

python validate_routing_bands_simple.py
# Should show:
#   ✓ Safety Check 1 passed (no phishing in auto-clear)
#   ⚠ Safety Check 2 (3 legit in auto-flag with 0.80)
#   Final verdict: Adjust to 0.85
```

## DEPLOYMENT

### 5. Apply Patch to gmail.py
```bash
# Backup current version
cp gmail.py gmail.py.backup

# Apply patch (see v2_patch_corrected.py for exact code)
# Replace lines 1036-1114 with V2 routing code
# CRITICAL: Ensure ml_confidence is preserved for DB writes
```

### 6. Restart Backend
```bash
# Kill existing process
pkill -f "uvicorn main:app"

# Start with logging
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info

# Watch logs for:
# [V2_ROUTER] Model loaded. Thresholds: auto-clear<0.40, auto-flag>0.85
```

### 7. Smoke Tests
Test with 3 emails (use FastAPI /analyze endpoint or frontend):

**Test 1: Obvious legitimate (expect auto-clear)**
```json
{
  "subject": "Lunch tomorrow?",
  "body": "Hey, want to grab lunch tomorrow? Let me know!",
  "sender": "friend@gmail.com"
}
```
Expected log: `[V2_ROUTER] ... AUTO-CLEAR (score=0.XX < 0.40)`

**Test 2: Modern service email (expect AI cascade)**
```json
{
  "subject": "Your Amazon order shipped",
  "body": "Your order #123 has shipped. Track: https://amazon.com/track",
  "sender": "shipment@amazon.com"
}
```
Expected log: `[V2_ROUTER] ... ROUTING TO AI CASCADE (score=0.XX in uncertain band)`

**Test 3: Obvious phishing (expect auto-flag)**
```json
{
  "subject": "URGENT: Verify NOW!!!",
  "body": "Account suspended! Click: http://192.168.1.1/verify Act now or deleted!",
  "sender": "phish@scam.tk"
}
```
Expected log: `[V2_ROUTER] ... AUTO-FLAG (score=0.XX > 0.85)`

## POST-DEPLOYMENT MONITORING

### 8. First Hour: Watch Logs
```bash
tail -f logs/app.log | grep -E '\[V2_ROUTER\]|\[ROUTING\]'
```

Look for:
- ✓ Routing decisions being logged
- ✓ Scores distributed across all 3 bands
- ✗ Errors loading V2 model
- ✗ All emails going to AI cascade (V2 not working)

### 9. First Day: Run Monitoring Queries
```sql
-- Routing distribution (see v2_monitoring_queries.py for full queries)
SELECT 
    CASE 
        WHEN source = 'v2' AND scam_score < 40 THEN 'v2_auto_clear'
        WHEN source = 'v2' AND scam_score > 85 THEN 'v2_auto_flag'
        WHEN source = 'ai' THEN 'ai_cascade'
        ELSE 'other'
    END as routing_path,
    COUNT(*) as count
FROM analyzed_emails
WHERE analyzed_at >= NOW() - INTERVAL '24 hours'
GROUP BY routing_path;
```

Expected distribution:
- v2_auto_clear: ~5-10%
- ai_cascade: ~85-90%
- v2_auto_flag: ~3-5%

### 10. First Week: Check for Issues

**Query 1: Legitimate emails near auto-flag threshold**
```sql
SELECT subject, sender, ml_confidence as v2_score
FROM analyzed_emails ae
JOIN email_labels el ON ae.label_id = el.id
WHERE source = 'v2'
  AND ml_confidence BETWEEN 0.80 AND 0.95
  AND el.name NOT IN ('Spam', 'Scam')
  AND analyzed_at >= NOW() - INTERVAL '7 days'
ORDER BY ml_confidence DESC;
```

If any legitimate scores > 0.85: **Raise threshold to 0.90 immediately**

**Query 2: False positives in auto-flag band**
```sql
SELECT COUNT(*) as false_positives
FROM analyzed_emails ae
JOIN email_labels el ON ae.label_id = el.id
WHERE source = 'v2'
  AND scam_score > 85
  AND el.name NOT IN ('Spam', 'Scam')
  AND analyzed_at >= NOW() - INTERVAL '7 days';
```

If > 2% false positive rate: **Raise threshold or disable auto-flag**

## ROLLBACK PROCEDURE

If V2 causes issues:

### Immediate Rollback (< 5 minutes)
```bash
# 1. Restore backup
cp gmail.py.backup gmail.py

# 2. Restart backend
pkill -f "uvicorn main:app"
uvicorn main:app --host 0.0.0.0 --port 8000

# 3. Verify all emails go to AI cascade
tail -f logs/app.log | grep '\[AI\]'
```

### Disable V2 Without Rollback
```python
# In v2_routing.py, line 16, change:
V2_AVAILABLE = False  # Force disable

# Restart backend - all emails will route to AI cascade
```

## SUCCESS CRITERIA

After 1 week of production:

✓ False positive rate < 2% in auto-flag band
✓ Zero legitimate emails scoring > 0.85
✓ AI cascade load reduced by 10-15%
✓ V2 vs AI disagreement rate < 15%
✓ No V2-related errors in logs

## TUNING

If after 1 week you see:

**Scenario A: Max legitimate score is 0.88**
- Action: Raise auto-flag threshold to 0.90
- Update: V2_AUTO_FLAG_THRESHOLD=0.90 in .env

**Scenario B: Too much AI cascade load (>95%)**
- Review: Are thresholds too conservative?
- Consider: Lowering auto-clear to 0.35 or raising auto-flag to 0.80

**Scenario C: V2 vs AI disagree often (>20%)**
- Investigation: Model drift or training data mismatch
- Action: Review disagreement logs, consider V3 retraining

## FILES CREATED

All documentation in backend/:

1. v2_routing.py - Production routing module
2. v2_patch_corrected.py - Exact patch for gmail.py
3. v2_monitoring_queries.py - SQL queries for monitoring
4. v2_capstone_writeup.py - Complete technical narrative
5. validate_routing_bands_simple.py - Threshold validation
6. test_short_informal_emails.py - Modern email test suite
7. V2_INTEGRATION_CAPSTONE.md - Markdown documentation

## NEXT STEPS AFTER STABLE

1. Collect 1000+ production V2 scores
2. Validate threshold against real traffic patterns
3. Build Grafana dashboard for routing metrics
4. Plan V3 retraining with modern service email samples
"""

if __name__ == "__main__":
    print(DEPLOYMENT_CHECKLIST)
