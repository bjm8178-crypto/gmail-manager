-- Migration 004: Create prefetched_emails dedicated staging buffer table
CREATE TABLE IF NOT EXISTS prefetched_emails (
    email_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    sender TEXT,
    subject TEXT,
    snippet TEXT,
    body TEXT,
    received_at TEXT,
    analysis_status TEXT DEFAULT 'pending',
    label_id INTEGER REFERENCES custom_labels(label_id) ON DELETE SET NULL,
    scam_score INTEGER,
    scam_indicators TEXT DEFAULT '[]',
    reasoning TEXT,
    routing_decision TEXT,
    provider_used TEXT,
    url_scan_status TEXT,
    urls_total INTEGER DEFAULT 0,
    urls_checked INTEGER DEFAULT 0,
    is_quarantined INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prefetched_emails_user_status 
    ON prefetched_emails (user_id, analysis_status);

-- Migrate existing legacy 'fetched' status rows from analyzed_emails to prefetched_emails
INSERT INTO prefetched_emails (
    email_id, user_id, sender, subject, snippet, body, received_at,
    analysis_status, label_id, scam_score, scam_indicators, reasoning,
    routing_decision, provider_used, url_scan_status, urls_total, urls_checked, is_quarantined
)
SELECT 
    email_id, user_id, sender, subject, snippet, body, received_at,
    COALESCE(analysis_status, 'pending'), label_id, scam_score, scam_indicators, reasoning,
    routing_decision, provider_used, url_scan_status, urls_total, urls_checked, is_quarantined
FROM analyzed_emails
WHERE status = 'fetched'
ON CONFLICT (email_id) DO NOTHING;

-- Clean up legacy 'fetched' status rows from analyzed_emails so analyzed_emails contains only labeled emails
DELETE FROM analyzed_emails WHERE status = 'fetched';
