"""
Step 3: Validate V2 confidence-band routing thresholds (simplified version)
Scores test emails on-the-fly, no CSV dependency
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from predict import predict_email

print('=' * 80)
print('STEP 3: CONFIDENCE-BAND ROUTING VALIDATION')
print('=' * 80)
print()

# Proposed routing bands
AUTO_CLEAR_THRESHOLD = 0.40
AUTO_FLAG_THRESHOLD = 0.80

print(f'Proposed routing bands:')
print(f'  Score < {AUTO_CLEAR_THRESHOLD:.2f}  → Auto-clear (legitimate, skip AI cascade)')
print(f'  Score {AUTO_CLEAR_THRESHOLD:.2f}-{AUTO_FLAG_THRESHOLD:.2f} → Route to AI cascade')
print(f'  Score > {AUTO_FLAG_THRESHOLD:.2f}  → Auto-flag (phishing, skip AI cascade)')
print()

# Build comprehensive test set
print('Building test set...')
print()

test_emails = [
    # LEGITIMATE EMAILS - Modern/short style (known V2 weakness)
    ('legitimate', 'Modern: Calendar reminder', 'Team sync tomorrow', 'Just a reminder - we have our team sync tomorrow at 2pm in Room B.', 'calendar@company.com'),
    ('legitimate', 'Modern: Quick reply', 'Re: Lunch plans', 'Sounds good, see you at 12:30!', 'sarah@company.com'),
    ('legitimate', 'Modern: Amazon order', 'Your Amazon.com order has shipped', 'Your order #112-3456789-1234567 has shipped. Track: https://amazon.com/track/12345', 'shipment-tracking@amazon.com'),
    ('legitimate', 'Modern: Password reset', 'Password reset requested', 'We received a request to reset your password. Click to confirm: https://accounts.example.com/reset/abc123', 'noreply@accounts.example.com'),
    ('legitimate', 'Modern: Payment', 'Payment received', 'Thank you for your payment of $150.00. Invoice #45678 is now paid.', 'billing@vendor.com'),
    ('legitimate', 'Modern: Newsletter', 'Welcome!', 'Thanks for subscribing! Weekly updates every Monday.', 'newsletter@company.com'),
    ('legitimate', 'Modern: Security alert', 'New login detected', 'New login from Windows device in NY. Secure your account if not you.', 'security@service.com'),
    ('legitimate', 'Modern: Internal update', 'Project update', 'Deadline moved to Friday. Questions?', 'manager@company.com'),
    ('legitimate', 'Modern: Delivery', 'Package arriving', 'FedEx package arrives today 2-6pm. Track: https://fedex.com/track/789', 'tracking@fedex.com'),
    ('legitimate', 'Modern: Event', 'Registration confirmed', 'Tech Conference 2026 confirmed. Details: https://conference.com/attendee/123', 'events@conference.com'),
    
    # LEGITIMATE EMAILS - Corpus style (longer, more formal)
    ('legitimate', 'Corpus: Meeting notes', 'Q3 Strategy Meeting Notes', 'Hi team, attached are the notes from our Q3 strategy meeting. Please review the action items and provide feedback by EOW. Key decisions included budget allocation for the new marketing campaign and timeline adjustments for product launch.', 'alice@company.com'),
    ('legitimate', 'Corpus: Project status', 'Project Alpha Status Update', 'Hello everyone, wanted to share a quick update on Project Alpha. We completed the first milestone ahead of schedule and are now moving into phase 2. The team has done excellent work so far. Looking forward to continuing this momentum.', 'bob@company.com'),
    ('legitimate', 'Corpus: Casual chat', 'Lunch tomorrow?', 'Hey! Want to grab lunch tomorrow? I was thinking that new place downtown. Let me know if you are free around noon!', 'friend@gmail.com'),
    
    # PHISHING EMAILS - Obvious
    ('phishing', 'Phishing: Urgent verify', 'URGENT: Verify Account NOW', 'Your account suspended! Click here immediately: http://192.168.1.1/verify or account deleted forever! Act now!!!', 'noreply@phish.tk'),
    ('phishing', 'Phishing: Lottery', 'You WON $1,000,000!!!', 'CONGRATULATIONS!!! Lucky winner! Claim prize NOW: http://scam-lottery.com/claim Limited time!!!', 'winner@scam.info'),
    ('phishing', 'Phishing: Nigerian', 'Urgent business proposal', 'Dear friend, I am prince from Nigeria. I have $10 million to transfer. I need your help. Please send bank details immediately. You receive 30% commission. God bless.', 'prince@nigeria.com'),
    ('phishing', 'Phishing: Fake bank', 'Security Alert from Bank', 'Unusual activity detected. Verify identity immediately or account locked: http://fake-bank.tk/verify Click here now!', 'security@bank-fake.com'),
    ('phishing', 'Phishing: Tax scam', 'IRS Final Notice', 'You owe $5000 in back taxes. Pay immediately or face arrest. Click here: http://irs-scam.com/pay Wire transfer only!', 'irs@scam.gov'),
]

print(f'Test set: {len(test_emails)} emails')
print(f'  Legitimate: {sum(1 for e in test_emails if e[0] == "legitimate")}')
print(f'  Phishing: {sum(1 for e in test_emails if e[0] == "phishing")}')
print()

# Score all emails
print('Scoring all emails...')
results = []

for true_label, name, subject, body, sender in test_emails:
    result = predict_email(subject, body, sender)
    score = result['probabilities']['phishing']
    
    results.append({
        'true_label': true_label,
        'name': name,
        'score': score,
        'subject': subject
    })

print(f'✓ Scored {len(results)} emails\n')

# Assign routing bands
def get_routing_band(score):
    if score < AUTO_CLEAR_THRESHOLD:
        return 'auto_clear'
    elif score > AUTO_FLAG_THRESHOLD:
        return 'auto_flag'
    else:
        return 'ai_cascade'

for r in results:
    r['routing_band'] = get_routing_band(r['score'])

# ============================================================================
# BAND DISTRIBUTION
# ============================================================================

print('=' * 80)
print('BAND DISTRIBUTION ANALYSIS')
print('=' * 80)
print()

from collections import Counter
band_counts = Counter(r['routing_band'] for r in results)

print('Overall Routing Band Distribution:')
for band in ['auto_clear', 'ai_cascade', 'auto_flag']:
    count = band_counts.get(band, 0)
    pct = count / len(results) * 100
    print(f'  {band:<15}: {count:3d} emails ({pct:5.1f}%)')
print()

# ============================================================================
# SAFETY CHECK 1: Auto-Clear Band
# ============================================================================

print('=' * 80)
print('SAFETY CHECK 1: Auto-Clear Band (< 0.40)')
print('=' * 80)
print()

auto_clear = [r for r in results if r['routing_band'] == 'auto_clear']
print(f'Total emails in auto-clear band: {len(auto_clear)}')

auto_clear_phishing = [r for r in auto_clear if r['true_label'] == 'phishing']
print(f'⚠ PHISHING EMAILS IN AUTO-CLEAR: {len(auto_clear_phishing)}')

if len(auto_clear_phishing) > 0:
    print(f'\n   ✗✗ SAFETY CHECK FAILED')
    print(f'   {len(auto_clear_phishing)} phishing emails would slip through!')
    print(f'\n   Details:')
    for r in auto_clear_phishing:
        print(f'     {r["name"]}: {r["score"]:.4f}')
    print(f'\n   → THRESHOLD TOO HIGH - MUST ADJUST')
else:
    print(f'   ✓ SAFETY CHECK PASSED')
    print(f'   Zero phishing in auto-clear band')

print()

# ============================================================================
# SAFETY CHECK 2: Auto-Flag Band
# ============================================================================

print('=' * 80)
print('SAFETY CHECK 2: Auto-Flag Band (> 0.80)')
print('=' * 80)
print()

auto_flag = [r for r in results if r['routing_band'] == 'auto_flag']
print(f'Total emails in auto-flag band: {len(auto_flag)}')

auto_flag_legit = [r for r in auto_flag if r['true_label'] == 'legitimate']
print(f'⚠ LEGITIMATE EMAILS IN AUTO-FLAG: {len(auto_flag_legit)}')

if len(auto_flag_legit) > 0:
    print(f'\n   ⚠⚠ REVIEW REQUIRED')
    print(f'   {len(auto_flag_legit)} legitimate emails would be auto-flagged')
    print(f'\n   Details:')
    for r in auto_flag_legit:
        print(f'     {r["name"]}: {r["score"]:.4f}')
    
    # Find safe threshold
    legit_scores = [r['score'] for r in results if r['true_label'] == 'legitimate']
    max_legit = max(legit_scores)
    suggested = min(0.95, max(0.85, max_legit + 0.01))
    
    print(f'\n   Max legitimate score: {max_legit:.4f}')
    print(f'   Suggested auto-flag threshold: {suggested:.2f}')
    print(f'\n   → THRESHOLD TOO LOW - RECOMMEND ADJUSTMENT')
else:
    print(f'   ✓ SAFETY CHECK PASSED')
    print(f'   Zero legitimate in auto-flag band')

print()

# ============================================================================
# AI CASCADE BAND
# ============================================================================

print('=' * 80)
print('AI CASCADE BAND (0.40-0.80)')
print('=' * 80)
print()

cascade = [r for r in results if r['routing_band'] == 'ai_cascade']
cascade_legit = sum(1 for r in cascade if r['true_label'] == 'legitimate')
cascade_phishing = sum(1 for r in cascade if r['true_label'] == 'phishing')

print(f'Emails routed to AI cascade: {len(cascade)}')
print(f'  Legitimate: {cascade_legit}')
print(f'  Phishing: {cascade_phishing}')
print(f'  AI cascade load: {len(cascade)/len(results)*100:.1f}% of traffic')
print()

# ============================================================================
# FINAL VERDICT
# ============================================================================

print('=' * 80)
print('FINAL VERDICT')
print('=' * 80)
print()

fn_autoclear = len(auto_clear_phishing)
fp_autoflag = len(auto_flag_legit)

if fn_autoclear == 0 and fp_autoflag == 0:
    print('✓✓✓ ROUTING BANDS ARE SAFE')
    print(f'    Auto-clear < {AUTO_CLEAR_THRESHOLD}: {len(auto_clear)} emails, 0 phishing')
    print(f'    AI cascade {AUTO_CLEAR_THRESHOLD}-{AUTO_FLAG_THRESHOLD}: {len(cascade)} emails ({len(cascade)/len(results)*100:.0f}%)')
    print(f'    Auto-flag > {AUTO_FLAG_THRESHOLD}: {len(auto_flag)} emails, 0 legitimate')
    print()
    print('    ✓ APPROVED FOR IMPLEMENTATION')
    
elif fn_autoclear > 0:
    print('✗✗ CRITICAL SAFETY FAILURE')
    print(f'   {fn_autoclear} phishing emails score < {AUTO_CLEAR_THRESHOLD}')
    print(f'   → Remove auto-clear path OR lower threshold to 0.20')
    print()
    print('   ✗ DO NOT IMPLEMENT')
    
elif fp_autoflag > 0:
    legit_scores = [r['score'] for r in results if r['true_label'] == 'legitimate']
    max_legit = max(legit_scores)
    suggested = min(0.95, max(0.85, max_legit + 0.01))
    
    print('⚠⚠ AUTO-FLAG THRESHOLD TOO LOW')
    print(f'   {fp_autoflag} legitimate emails score > {AUTO_FLAG_THRESHOLD}')
    print(f'   (Modern service emails - known V2 weakness)')
    print()
    print(f'   RECOMMENDED ADJUSTMENTS:')
    print(f'   Option A: Raise auto-flag to {suggested:.2f}')
    print(f'   Option B: Remove auto-flag (all >0.40 go to cascade)')
    print()
    print('   ⚠ ADJUST BEFORE IMPLEMENTATION')

print()
print('=' * 80)
