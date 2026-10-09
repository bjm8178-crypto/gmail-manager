"""
Integration plan for V2 confidence-band routing in gmail.py

This shows where and how to integrate v2_routing.py into the existing
analyze_single_email_internal() function in gmail.py.

CURRENT FLOW (lines 1036-1114):
1. ML model runs first (ml_inference.py)
2. If ML confident → use ML result
3. If ML escalates OR no model → call AI cascade
4. Parse AI response

NEW FLOW WITH V2 ROUTING:
1. V2 routing module runs first
2. Based on V2 score:
   - < 0.40: Return V2 result (auto-clear)
   - > 0.85: Return V2 result (auto-flag)
   - 0.40-0.85: Call AI cascade
3. Parse final result

CHANGES NEEDED:
- Replace current ML inference call (lines 1042-1059)
- Replace AI cascade call (lines 1062-1078)
- Keep everything else (validation, quarantine logic, DB writes)
"""

# ============================================================================
# STEP 4: Integration Code
# ============================================================================

INTEGRATION_INSTRUCTIONS = """
In gmail.py, function analyze_single_email_internal(), 
REPLACE lines 1036-1100 with the following:
"""

NEW_CODE_BLOCK = '''
            # Step C — V2 ML Confidence-Band Routing (Phase 7)
            # Replaces old ML inference + AI cascade logic
            from v2_routing import route_email_with_v2
            
            # Define AI cascade as a closure for v2_routing to call
            async def run_ai_cascade():
                """Closure that calls AI cascade with current email context."""
                prompt = classification_prompt.format(
                    sender=sender,
                    subject=subject,
                    body=body[:1500],
                    url_threat_confirmed=url_threat_confirmed,
                    url_scan_unavailable=url_scan_unavailable,
                    available_labels=", ".join(available_label_names),
                )
                
                t0 = time.perf_counter()
                ai_result = await ai_router.analyze_json(prompt)
                nonlocal t_ai_call
                t_ai_call = time.perf_counter() - t0
                
                return ai_result
            
            # Route through V2 confidence-band system
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
            
            # Extract results from routing
            label = routing_result['label']
            scam_score = routing_result['scam_score']
            scam_indicators = routing_result['scam_indicators']
            reasoning = routing_result['reasoning']
            provider_used = routing_result.get('provider_used')
            routing_decision = routing_result['routing_decision']
            source = 'v2' if routing_decision.startswith('v2_') else 'ai'
            
            # Log routing decision
            logger.info(f"[ROUTING] {email_id[:12]}... decision={routing_decision}, label={label}, score={scam_score}")
'''

VALIDATION_NOTE = """
KEEP EXISTING CODE AFTER LINE 1100:
- Step E: Validate AI/ML output (lines 1116-1137)
- Step F: Determine quarantine flag (lines 1152-1156)
- Step G: Resolve label_id (line 1159)
- Step H: Save to database (lines 1162-1208)
- Step I: Apply Gmail label (lines 1210-1230)

All downstream logic remains unchanged - v2_routing returns same structure.
"""

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

ENV_VARIABLES = """
Add to .env file:

# V2 ML Model Confidence-Band Routing
V2_AUTO_CLEAR_THRESHOLD=0.40
V2_AUTO_FLAG_THRESHOLD=0.85

These control routing behavior:
- Scores < 0.40: Auto-clear (legitimate, skip AI)
- Scores 0.40-0.85: Route to AI cascade
- Scores > 0.85: Auto-flag (phishing, skip AI)

Thresholds validated in validate_routing_bands_simple.py
"""

# ============================================================================
# TESTING CHECKLIST
# ============================================================================

TESTING_CHECKLIST = """
After integration, test with these scenarios:

1. Low-confidence legitimate (score 0.10-0.30)
   → Should auto-clear, source='v2', routing_decision='v2_auto_clear'

2. Modern service email (score 0.60-0.80)
   → Should route to AI cascade, source='ai', routing_decision='ai_cascade'

3. High-confidence phishing (score 0.90-0.99)
   → Should auto-flag, source='v2', routing_decision='v2_auto_flag'

4. V2 model file missing
   → Should fall back to AI cascade for all emails

5. AI cascade failure in uncertain band
   → Should use V2 prediction as fallback

Monitor logs for:
- [V2_ROUTER] messages showing routing decisions
- [ROUTING] messages showing final outcome
- Disagreement logs when V2 and AI diverge
"""

if __name__ == "__main__":
    print("=" * 80)
    print("V2 ROUTING INTEGRATION PLAN")
    print("=" * 80)
    print()
    print(__doc__)
    print()
    print(INTEGRATION_INSTRUCTIONS)
    print(NEW_CODE_BLOCK)
    print()
    print("=" * 80)
    print("VALIDATION NOTE")
    print("=" * 80)
    print(VALIDATION_NOTE)
    print()
    print("=" * 80)
    print("ENVIRONMENT VARIABLES")
    print("=" * 80)
    print(ENV_VARIABLES)
    print()
    print("=" * 80)
    print("TESTING CHECKLIST")
    print("=" * 80)
    print(TESTING_CHECKLIST)
