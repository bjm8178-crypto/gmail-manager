"""
Phase 2: Feature Extraction Module
Pure functions for extracting ML features from email data.
No DB/network calls - designed for unit testing.
"""
import re
from typing import Dict, Any, List
from urllib.parse import urlparse
import json


def extract_features(
    subject: str,
    sender: str,
    body: str,
    snippet: str = None,
    has_list_unsubscribe: bool = False,
    spf_pass: bool = True,
    dkim_pass: bool = True,
    sender_history: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Extract feature vector from email for ML model.
    
    IMPORTANT: No AI-produced labels or scores allowed as inputs (feature leakage prevention).
    
    Args:
        subject: Email subject line
        sender: Email sender address
        body: Email body text
        snippet: Short preview text (optional)
        has_list_unsubscribe: Whether List-Unsubscribe header present
        spf_pass: SPF validation result
        dkim_pass: DKIM validation result
        sender_history: Historical stats for this sender {sent_count, scam_count, avg_score}
    
    Returns:
        Dictionary of features safe for ML input
    """
    text_content = f"{subject or ''} {body or ''} {snippet or ''}".lower()
    
    features = {
        # Text length signals
        'subject_length': len(subject or ''),
        'body_length': len(body or ''),
        'has_body': 1 if body and len(body.strip()) > 0 else 0,
        
        # URL signals
        'url_count': _count_urls(body or ''),
        'has_shortened_url': 1 if _has_shortened_url(body or '') else 0,
        'suspicious_tld': 1 if _has_suspicious_tld(body or '') else 0,
        
        # Urgency/pressure language
        'urgency_score': _compute_urgency_score(text_content),
        
        # Sender signals
        'sender_domain': _extract_domain(sender),
        'sender_is_freemail': 1 if _is_freemail(sender) else 0,
        'sender_display_mismatch': 1 if _has_display_name_mismatch(sender) else 0,
        
        # Authentication signals (structural, not spoofable by text)
        'spf_pass': 1 if spf_pass else 0,
        'dkim_pass': 1 if dkim_pass else 0,
        'has_list_unsubscribe': 1 if has_list_unsubscribe else 0,
        
        # Sender reputation (supporting signal only, never sufficient alone)
        'sender_email_count': sender_history.get('sent_count', 0) if sender_history else 0,
        'sender_scam_rate': sender_history.get('scam_count', 0) / max(sender_history.get('sent_count', 1), 1) if sender_history else 0,
        'sender_avg_score': sender_history.get('avg_score', 0.5) if sender_history else 0.5,
        
        # Money/financial keywords
        'has_money_keywords': 1 if _has_money_keywords(text_content) else 0,
        
        # Call-to-action intensity
        'cta_count': _count_cta_phrases(text_content),
    }
    
    return features


def _count_urls(text: str) -> int:
    """Count HTTP(S) URLs in text."""
    return len(re.findall(r'https?://[^\s]+', text, re.IGNORECASE))


def _has_shortened_url(text: str) -> bool:
    """Check for common URL shorteners."""
    shorteners = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'short.link']
    text_lower = text.lower()
    return any(shortener in text_lower for shortener in shorteners)


def _has_suspicious_tld(text: str) -> bool:
    """Check for TLDs commonly used in scams."""
    suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.gq', '.xyz', '.top', '.loan', '.work']
    urls = re.findall(r'https?://[^\s]+', text, re.IGNORECASE)
    return any(any(url.lower().endswith(tld) for tld in suspicious_tlds) for url in urls)


def _compute_urgency_score(text: str) -> float:
    """
    Compute urgency score based on pressure language.
    Returns 0.0-1.0 scale.
    """
    urgency_patterns = [
        r'urgent', r'immediately', r'act now', r'limited time', r'expires',
        r'verify.*account', r'suspend.*account', r'unusual.*activity',
        r'confirm.*identity', r'click here now', r'respond within',
        r'last chance', r'final notice', r'action required'
    ]
    
    matches = sum(1 for pattern in urgency_patterns if re.search(pattern, text, re.IGNORECASE))
    return min(matches / 5.0, 1.0)


def _extract_domain(email: str) -> str:
    """Extract domain from email address."""
    match = re.search(r'@([^\s>]+)', email)
    return match.group(1).lower() if match else ''


def _is_freemail(email: str) -> bool:
    """Check if sender uses free email provider."""
    freemail_domains = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
        'aol.com', 'icloud.com', 'mail.com', 'protonmail.com'
    ]
    domain = _extract_domain(email)
    return domain in freemail_domains


def _has_display_name_mismatch(sender: str) -> bool:
    """
    Detect potential display name spoofing.
    Example: "PayPal <scammer@evil.com>" where display != domain
    """
    match = re.match(r'([^<]+)<([^>]+)>', sender)
    if not match:
        return False
    
    display_name = match.group(1).strip().lower()
    email_address = match.group(2).strip().lower()
    domain = _extract_domain(email_address)
    
    suspicious_brands = ['paypal', 'amazon', 'microsoft', 'apple', 'google', 'bank', 'netflix']
    
    for brand in suspicious_brands:
        if brand in display_name and brand not in domain:
            return True
    
    return False


def _has_money_keywords(text: str) -> bool:
    """Check for financial/monetary keywords."""
    money_keywords = [
        r'\$\d+', r'payment', r'invoice', r'refund', r'transfer', 
        r'wire', r'bank account', r'credit card', r'social security',
        r'tax', r'irs', r'prize', r'lottery', r'claim.*money'
    ]
    return any(re.search(keyword, text, re.IGNORECASE) for keyword in money_keywords)


def _count_cta_phrases(text: str) -> int:
    """Count call-to-action phrases."""
    cta_patterns = [
        r'click here', r'download now', r'verify', r'confirm',
        r'update.*information', r'review.*account', r'sign in'
    ]
    return sum(1 for pattern in cta_patterns if re.search(pattern, text, re.IGNORECASE))


def get_sender_history(sender: str, conn) -> Dict[str, Any]:
    """
    Query historical statistics for a sender.
    Called separately from feature extraction to keep features.py DB-free.
    
    Args:
        sender: Email address
        conn: Database connection
    
    Returns:
        Dict with sent_count, scam_count, avg_score
    """
    from database import _execute
    
    cursor = conn.cursor()
    # Exclude AI-sourced emails to prevent label leakage in training features
    # Only human-labeled or ML-labeled emails contribute to sender history
    _execute(cursor, """
        SELECT 
            COUNT(*) as sent_count,
            SUM(CASE WHEN scam_score >= 60 THEN 1 ELSE 0 END) as scam_count,
            AVG(scam_score) as avg_score
        FROM analyzed_emails
        WHERE sender = %s AND scam_score IS NOT NULL AND source != 'ai'
    """, (sender,))
    
    row = cursor.fetchone()
    if row:
        sent_count = row['sent_count'] if isinstance(row, dict) else row[0]
        scam_count = row['scam_count'] if isinstance(row, dict) else row[1]
        avg_score = row['avg_score'] if isinstance(row, dict) else row[2]
        
        if sent_count and sent_count > 0:
            return {
                'sent_count': sent_count or 0,
                'scam_count': scam_count or 0,
                'avg_score': float(avg_score) if avg_score is not None else 0.5
            }
    
    return {'sent_count': 0, 'scam_count': 0, 'avg_score': 0.5}
