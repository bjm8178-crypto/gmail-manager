"""
V2 Integration: Corrected Patch for gmail.py
Fixes ml_confidence preservation for database writes
"""

CORRECTED_PATCH = """
================================================================================
CORRECTED PATCH FOR gmail.py
Lines 1036-1114 (79 lines) → Replace with lines below (52 lines)
================================================================================

REPLACE THIS SECTION (Lines 1036-1114):
----------------------------------------
            # Step C — ML model pre-filter (Phase 6: hybrid routing)
            ml_prediction = None
            ml_confidence = 0.0
            ...
            # (all code through line 1114)

WITH THIS:
----------
            # Step C — V2 ML Confidence-Band Routing (Phase 7)
            from v2_routing import route_email_with_v2
            
            # AI cascade closure for v2_routing
            async def run_ai_cascade():
                prompt = classification_prompt.format(
                    sender=sender,
                    subject=subject,
                    body=body[:1500],
                    url_threat_confirmed=url_threat_confirmed,
                    url_scan_unavailable=url_scan_unavailable,
                    available_labels=", ".join(available_label_names),
                )
                
                nonlocal t_ai_call
                t0 = time.perf_counter()
                ai_result = await ai_router.analyze_json(prompt)
                t_ai_call = time.perf_counter() - t0
                
                return ai_result
            
            # Route through V2 confidence bands
            routing_result = await route_email_with_v2(
                email_id=email_id,
                subject=subject,
                sender=sender,
                body=body,
                snippet=snippet,
                ai_cascade_func=run_ai_cascade,
                classification_prompt=classification_prompt,
                url_threat_confirmed=url_threat_confirmed,
                url_scan_unavailable=url_scan_unavailable,
                available_label_names=available_label_names
            )
            
            # Extract results
            label = routing_result['label']
            scam_score = routing_result['scam_score']
            scam_indicators = routing_result['scam_indicators']
            reasoning = routing_result.get('reasoning', '')
            provider_used = routing_result.get('provider_used')
            source = 'v2' if routing_result['routing_decision'].startswith('v2_') else 'ai'
            
            # CRITICAL: Preserve ml_confidence for database writes
            # For V2 paths: store V2 phishing probability (0-1 scale)
            # For AI paths: None (no ML confidence available)
            ml_confidence = routing_result.get('v2_score') if source == 'v2' else None
            
            logger.info(f"[ROUTING] {email_id[:12]}... decision={routing_result['routing_decision']}, label={label}, score={scam_score}, v2_score={ml_confidence}")

            # Step E — Validate AI/ML output (LINE 1116 - UNCHANGED BELOW)

================================================================================
VERIFICATION CHECKLIST
================================================================================

After applying patch, verify:

1. ✓ V2 module imports correctly
   - Run: python -c "from v2_routing import route_email_with_v2; print('OK')"

2. ✓ Environment variables set in .env:
   V2_AUTO_CLEAR_THRESHOLD=0.40
   V2_AUTO_FLAG_THRESHOLD=0.85

3. ✓ scam_classifier_v2.pkl exists in backend/
   - File size: ~12.5 MB
   - Run: python -c "import joblib; joblib.load('scam_classifier_v2.pkl'); print('OK')"

4. ✓ Database fields accept ml_confidence (can be NULL for AI paths)
   - Check: analyzed_emails.ml_confidence column type

5. ✓ Test with sample email:
   - Low score (< 0.40): Should log 'v2_auto_clear'
   - Mid score (0.40-0.85): Should log 'ai_cascade'
   - High score (> 0.85): Should log 'v2_auto_flag'

================================================================================
ROLLBACK PLAN (if issues arise)
================================================================================

If V2 causes problems, immediate rollback:

1. Comment out import: # from v2_routing import route_email_with_v2
2. Revert to old code (keep backup of lines 1036-1114)
3. Restart backend
4. All emails will fall back to AI cascade (existing behavior)

OR

Set environment variable to disable V2:
  V2_AVAILABLE=false (modify v2_routing.py to check this)
"""

if __name__ == "__main__":
    print(CORRECTED_PATCH)
