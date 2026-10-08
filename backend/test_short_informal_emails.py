"""
Test V2 on short/informal modern legitimate emails
Check if model has a blind spot for non-corpus-style emails
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from predict import predict_email

print('=' * 80)
print('V2 TEST: SHORT/INFORMAL MODERN LEGITIMATE EMAILS')
print('=' * 80)
print()

# Build realistic short/informal legitimate email test set
# Designed to mirror actual modern Gmail traffic, not formal business corpus
test_emails = [
    {
        'name': '1. Calendar meeting reminder (1 line)',
        'subject': 'Team sync tomorrow',
        'body': 'Just a reminder - we have our team sync tomorrow at 2pm in Room B.',
        'sender': 'calendar@company.com'
    },
    {
        'name': '2. Quick coworker reply',
        'subject': 'Re: Lunch plans',
        'body': 'Sounds good, see you at 12:30!',
        'sender': 'sarah@company.com'
    },
    {
        'name': '3. Amazon order shipped',
        'subject': 'Your Amazon.com order has shipped',
        'body': 'Your order #112-3456789-1234567 has shipped. Track your package: https://amazon.com/track/12345',
        'sender': 'shipment-tracking@amazon.com'
    },
    {
        'name': '4. Password reset confirmation (has urgency + link)',
        'subject': 'Password reset requested',
        'body': 'We received a request to reset your password. Click here to confirm: https://accounts.example.com/reset/abc123. If you did not request this, please ignore.',
        'sender': 'noreply@accounts.example.com'
    },
    {
        'name': '5. Payment confirmation',
        'subject': 'Payment received - Invoice #45678',
        'body': 'Thank you for your payment of $150.00. Invoice #45678 is now paid in full.',
        'sender': 'billing@vendor.com'
    },
    {
        'name': '6. Newsletter subscription confirmed',
        'subject': 'Welcome to our newsletter!',
        'body': 'Thanks for subscribing! You will receive our weekly updates every Monday.',
        'sender': 'newsletter@company.com'
    },
    {
        'name': '7. Login security alert (has urgent words)',
        'subject': 'New login from Windows device',
        'body': 'We detected a new login to your account from a Windows device in New York. If this was not you, please secure your account immediately.',
        'sender': 'security@service.com'
    },
    {
        'name': '8. Quick internal update',
        'subject': 'Update on project',
        'body': 'The deadline has been moved to Friday. Let me know if you have any questions.',
        'sender': 'manager@company.com'
    },
    {
        'name': '9. Delivery notification',
        'subject': 'Your package will arrive today',
        'body': 'Your FedEx package will arrive today between 2-6pm. Track here: https://fedex.com/track/789456',
        'sender': 'tracking@fedex.com'
    },
    {
        'name': '10. Event confirmation (has link)',
        'subject': 'Event registration confirmed',
        'body': 'Your registration for Tech Conference 2026 is confirmed. View details: https://conference.com/attendee/12345',
        'sender': 'events@conference.com'
    },
    {
        'name': '11. Receipt from online service',
        'subject': 'Receipt for your purchase',
        'body': 'Thanks for your purchase! Total: $29.99. Download receipt: https://service.com/receipt/xyz789',
        'sender': 'receipts@service.com'
    },
    {
        'name': '12. Friend invitation (very informal)',
        'subject': 'Dinner tonight?',
        'body': 'Hey! Want to grab dinner tonight around 7? Let me know!',
        'sender': 'friend@gmail.com'
    },
    {
        'name': '13. System maintenance notice',
        'subject': 'Scheduled maintenance tonight',
        'body': 'Our systems will undergo scheduled maintenance tonight from 11pm-1am. You may experience brief interruptions.',
        'sender': 'admin@company.com'
    },
    {
        'name': '14. Calendar invite (has action word)',
        'subject': 'Action required: Accept calendar invite',
        'body': 'Please accept the calendar invite for the Q4 planning meeting on Friday at 3pm.',
        'sender': 'calendar@company.com'
    },
    {
        'name': '15. Order ready for pickup',
        'subject': 'Your order is ready!',
        'body': 'Your order #12345 is ready for pickup at our Downtown location. Bring your confirmation email.',
        'sender': 'orders@store.com'
    },
    {
        'name': '16. Subscription renewal',
        'subject': 'Your subscription will renew soon',
        'body': 'Your annual subscription will automatically renew on March 15 for $99.99. Update payment: https://account.service.com/billing',
        'sender': 'billing@service.com'
    },
    {
        'name': '17. Support ticket update',
        'subject': 'Support ticket #789 updated',
        'body': 'We have updated your support ticket. View the latest response: https://support.company.com/ticket/789',
        'sender': 'support@company.com'
    },
    {
        'name': '18. Flight check-in reminder (urgency)',
        'subject': 'Check in now for your flight',
        'body': 'Your flight to LAX departs in 24 hours. Check in now: https://airline.com/checkin/ABC123',
        'sender': 'noreply@airline.com'
    }
]

print(f'Testing {len(test_emails)} short/informal modern legitimate emails')
print('=' * 80)
print()

results = []

for i, email in enumerate(test_emails, 1):
    result = predict_email(email['subject'], email['body'], email['sender'])
    
    score = result.get('phishing_probability', {}).get('phishing', result.get('risk_score', 0) / 100)
    if isinstance(score, dict):
        score = score.get('phishing', 0)
    
    # Get actual phishing probability from probabilities dict
    if 'probabilities' in result:
        score = result['probabilities']['phishing']
    
    label = result.get('label', 'unknown')
    correct = (label == 'legitimate')
    
    results.append({
        'name': email['name'],
        'score': score,
        'label': label,
        'correct': correct,
        'subject': email['subject']
    })
    
    status = '✓' if correct else '✗'
    print(f"{email['name']}")
    print(f"  Subject: {email['subject']}")
    print(f"  Score: {score:.4f} | Label: {label} | {status}")
    print()

# Summary statistics
print('=' * 80)
print('RESULTS SUMMARY')
print('=' * 80)
print()

scores = [r['score'] for r in results]
correct_count = sum(1 for r in results if r['correct'])
false_positives = [r for r in results if not r['correct']]

print(f'Total emails tested: {len(results)}')
print(f'Correctly classified: {correct_count}/{len(results)} ({correct_count/len(results)*100:.1f}%)')
print(f'False positives: {len(false_positives)} ({len(false_positives)/len(results)*100:.1f}%)')
print()

print('Score Distribution:')
print(f'  Min:    {min(scores):.4f}')
print(f'  Q1:     {sorted(scores)[len(scores)//4]:.4f}')
print(f'  Median: {sorted(scores)[len(scores)//2]:.4f}')
print(f'  Mean:   {sum(scores)/len(scores):.4f}')
print(f'  Q3:     {sorted(scores)[3*len(scores)//4]:.4f}')
print(f'  Max:    {max(scores):.4f}')
print()

# Compare to corpus validation (from earlier test)
corpus_legit_mean = 0.1543
corpus_legit_median = 0.0899

modern_mean = sum(scores) / len(scores)
modern_median = sorted(scores)[len(scores) // 2]

print('Comparison to Corpus-Style Legitimate Emails:')
print(f'  Corpus legitimate mean:   {corpus_legit_mean:.4f}')
print(f'  Modern/short email mean:  {modern_mean:.4f}')
print(f'  Difference:               {modern_mean - corpus_legit_mean:+.4f}')
print()
print(f'  Corpus legitimate median: {corpus_legit_median:.4f}')
print(f'  Modern/short email median:{modern_median:.4f}')
print(f'  Difference:               {modern_median - corpus_legit_median:+.4f}')
print()

# Detailed false positive analysis
if len(false_positives) > 0:
    print('=' * 80)
    print('FALSE POSITIVE ANALYSIS')
    print('=' * 80)
    print()
    
    print(f'The following {len(false_positives)} emails were incorrectly flagged as phishing:')
    print()
    
    for fp in false_positives:
        print(f"  {fp['name']}")
        print(f"    Subject: {fp['subject']}")
        print(f"    Score: {fp['score']:.4f}")
        print()

# Verdict
print('=' * 80)
print('VERDICT')
print('=' * 80)
print()

if len(false_positives) == 0:
    print('✓✓✓ EXCELLENT: All short/informal emails correctly classified')
    print('    No blind spot detected. Safe to proceed with FastAPI integration.')
elif len(false_positives) <= 2:
    print('✓✓ GOOD: Only minor false positives on edge cases')
    print(f'   {len(false_positives)}/{len(results)} false positives ({len(false_positives)/len(results)*100:.1f}%)')
    print('   Acceptable for production deployment.')
elif len(false_positives) <= 5:
    print('⚠ MODERATE: Some false positives on short/informal emails')
    print(f'  {len(false_positives)}/{len(results)} false positives ({len(false_positives)/len(results)*100:.1f}%)')
    print('  Consider routing borderline scores (0.40-0.60) to AI cascade for review.')
else:
    print('✗✗ SIGNIFICANT BLIND SPOT DETECTED')
    print(f'  {len(false_positives)}/{len(results)} false positives ({len(false_positives)/len(results)*100:.1f}%)')
    print('  Model struggles with short/informal modern emails.')
    print('  Requires feature engineering fixes or threshold adjustment before production.')

print()
print('=' * 80)
print('TEST COMPLETE')
print('=' * 80)
