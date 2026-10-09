"""
Diagnostic script for AI category classification using production code path.
Tests route_email_with_v2 with 20 synthetic emails.
"""
import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from database import _get_connection, _release_connection
from v2_routing import route_email_with_v2
from ai_router import ai_router, CLASSIFICATION_PROMPT


async def diagnose():
    """Run 20 synthetic emails through route_email_with_v2."""
    
    # Fetch available label names from custom_labels table
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute('SELECT label_name FROM custom_labels ORDER BY label_name')
    rows = cur.fetchall()
    available_label_names = [row['label_name'] for row in rows]
    cur.close()
    _release_connection(conn)
    
    # 20 synthetic emails (never use real email content)
    emails = [
        # Short emails
        ("Account alert", "alerts@bank.test", "Your password was changed."),
        ("Weekly newsletter", "news@company.test", "This week's top stories."),
        ("Meeting reminder", "calendar@corp.test", "Meeting at 3pm today."),
        ("Receipt for order", "orders@shop.test", "Thank you for your purchase."),
        ("Friend invitation", "social@network.test", "John wants to connect."),
        ("Spam offer", "deals@spam.test", "Win a free vacation now!"),
        ("Work project update", "team@work.test", "Project status report attached."),
        ("Finance report", "finance@corp.test", "Q3 earnings summary."),
        ("Personal note", "friend@example.test", "Let's catch up this weekend."),
        ("Promotional sale", "sales@store.test", "50% off everything today."),
        
        # Long emails (near 6000 characters)
        ("Annual report", "ir@company.test", "A" * 5900),
        ("Legal document", "legal@firm.test", "B" * 5950),
        ("Product catalog", "catalog@vendor.test", "C" * 5980),
        
        # Medium emails
        ("Invoice #12345", "billing@service.test", "Your monthly invoice is ready. " * 50),
        ("Newsletter digest", "digest@news.test", "Today's headlines include " * 60),
        ("Social notification", "notify@social.test", "You have 10 new messages. " * 40),
        ("Spam lottery", "lottery@scam.test", "You won $1,000,000! Claim now! " * 70),
        ("Work announcement", "hr@company.test", "Company policy updates: " * 80),
        ("Finance statement", "statements@bank.test", "Account balance summary: " * 55),
        ("Personal email", "mom@family.test", "Hope you're doing well. " * 65),
    ]
    
    # Capture V2_ROUTER warnings
    v2_warnings = []
    
    class WarningCapture(logging.Handler):
        def emit(self, record):
            if record.name == 'v2_routing' and record.levelno == logging.WARNING:
                v2_warnings.append(record.getMessage())
    
    logger = logging.getLogger('v2_routing')
    handler = WarningCapture()
    logger.addHandler(handler)
    
    async def run_one(idx, subject, sender, body):
        """Run one email through route_email_with_v2."""
        email_id = f"test_{idx:03d}"
        
        async def ai_cascade_func():
            prompt = CLASSIFICATION_PROMPT.format(
                sender=sender,
                subject=subject,
                body=body[:6000],
                url_threat_confirmed=False,
                url_scan_unavailable=False,
                available_labels=", ".join(available_label_names),
            )
            return await ai_router.analyze_json(prompt)
        
        try:
            result = await route_email_with_v2(
                email_id=email_id,
                subject=subject,
                sender=sender,
                body=body,
                snippet=body[:200],
                ai_cascade_func=ai_cascade_func,
                classification_prompt=CLASSIFICATION_PROMPT,
                url_threat_confirmed=False,
                url_scan_unavailable=False,
                available_label_names=available_label_names,
            )
            return result
        except Exception as e:
            return {
                'category_status': 'error',
                'analysis_status': 'error',
                'provider_used': None,
                'routing_decision': 'error',
                'error': str(e)[:100],
            }
    
    tasks = [run_one(i, subj, sender, body) for i, (subj, sender, body) in enumerate(emails)]
    results = await asyncio.gather(*tasks)
    
    logger.removeHandler(handler)
    
    # Count category_status
    category_counts = {}
    for r in results:
        status = r.get('category_status', 'unknown')
        category_counts[status] = category_counts.get(status, 0) + 1
    
    # Count analysis_status
    analysis_counts = {}
    for r in results:
        status = r.get('analysis_status', 'unknown')
        analysis_counts[status] = analysis_counts.get(status, 0) + 1
    
    # Count provider_used
    provider_counts = {}
    for r in results:
        prov = r.get('provider_used') or 'None'
        provider_counts[prov] = provider_counts.get(prov, 0) + 1
    
    # Count routing_decision
    routing_counts = {}
    for r in results:
        dec = r.get('routing_decision', 'unknown')
        routing_counts[dec] = routing_counts.get(dec, 0) + 1
    
    # Group V2_ROUTER warnings by reason
    warning_groups = {}
    for msg in v2_warnings:
        # Extract reason (first part before colon or full message)
        reason = msg.split(':')[0] if ':' in msg else msg[:80]
        warning_groups[reason] = warning_groups.get(reason, 0) + 1
    
    print("=" * 60)
    print("DIAGNOSTIC: 20 Synthetic Emails via route_email_with_v2")
    print("=" * 60)
    print(f"Available labels: {available_label_names}")
    print()
    print("category_status counts:")
    for status, count in sorted(category_counts.items()):
        print(f"  {status}: {count}")
    print()
    print("analysis_status counts:")
    for status, count in sorted(analysis_counts.items()):
        print(f"  {status}: {count}")
    print()
    print("provider_used distribution:")
    for prov, count in sorted(provider_counts.items()):
        print(f"  {prov}: {count}")
    print()
    print("routing_decision distribution:")
    for dec, count in sorted(routing_counts.items()):
        print(f"  {dec}: {count}")
    print()
    print("V2_ROUTER warnings grouped by reason:")
    if warning_groups:
        for reason, count in sorted(warning_groups.items()):
            print(f"  {reason}: {count}")
    else:
        print("  (none)")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(diagnose())
