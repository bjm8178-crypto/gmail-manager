"""
Diagnostic script for AI category classification.
Tests the exact classification prompt and AI cascade used by analyze_email.
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from database import _get_connection, _release_connection
from ai_router import ai_router, CLASSIFICATION_PROMPT
from ai_response_schema import safe_extract_classification


async def diagnose():
    """Run one synthetic email through the AI cascade."""
    
    # Fetch available label names from custom_labels table
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute('SELECT label_name FROM custom_labels ORDER BY label_name')
    rows = cur.fetchall()
    available_label_names = [row['label_name'] for row in rows]
    cur.close()
    _release_connection(conn)
    
    # Synthetic email (never use real email content)
    subject = "Your account statement is ready"
    sender = "no-reply@example.com"
    body = "Your monthly statement for October is available in your online banking portal."
    
    # Build the exact prompt used by analyze_email
    prompt = CLASSIFICATION_PROMPT.format(
        sender=sender,
        subject=subject,
        body=body[:6000],
        url_threat_confirmed=False,
        url_scan_unavailable=False,
        available_labels=", ".join(available_label_names),
    )
    
    print("=" * 60)
    print("DIAGNOSTIC: AI Category Classification")
    print("=" * 60)
    print(f"Available labels: {available_label_names}")
    print(f"Prompt length: {len(prompt)} chars")
    print()
    
    # Run the AI cascade
    try:
        ai_result = await ai_router.analyze_json(prompt)
        
        print(f"provider_used: {ai_result.get('provider_used')}")
        print(f"result is dict: {isinstance(ai_result, dict)}")
        
        if isinstance(ai_result, dict):
            data = ai_result.get('data')
            print(f"keys under 'data': {list(data.keys()) if isinstance(data, dict) else 'NOT A DICT'}")
            
            if isinstance(data, dict):
                label = data.get('label')
                print(f"raw 'label' value: {repr(label[:40] if isinstance(label, str) else label)}")
                
                # Check case-insensitive match
                label_match = next(
                    (name for name in available_label_names
                     if isinstance(name, str) and isinstance(label, str)
                     and name.strip() and name.casefold() == label.strip().casefold()),
                    None
                )
                print(f"matches available label (case-insensitive): {label_match is not None} -> {label_match}")
                
                # Show safe_extract_classification result if available
                try:
                    extracted = safe_extract_classification(ai_result)
                    print(f"safe_extract_classification result keys: {list(extracted.keys()) if isinstance(extracted, dict) else 'NOT A DICT'}")
                except Exception as extract_err:
                    print(f"safe_extract_classification raised: {type(extract_err).__name__}: {str(extract_err)[:80]}")
            else:
                print("data is not a dict — cannot extract label")
        else:
            print("ai_result is not a dict")
            
    except Exception as e:
        print(f"AI cascade raised exception:")
        print(f"  Exception class: {type(e).__name__}")
        print(f"  Message (truncated): {str(e)[:120]}")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(diagnose())
