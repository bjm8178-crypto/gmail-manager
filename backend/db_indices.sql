-- db_indices.sql — Database Indices for Performance Optimization
-- Add these indices to speed up common queries in Gmail Manager

-- Analyzed Emails Indices
-- Most queries filter by user_id first, then various combinations
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_user_id ON analyzed_emails(user_id);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_user_status ON analyzed_emails(user_id, status);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_user_quarantined ON analyzed_emails(user_id, is_quarantined);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_user_scam_score ON analyzed_emails(user_id, scam_score);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_analyzed_at ON analyzed_emails(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_sender ON analyzed_emails(sender);
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_label_id ON analyzed_emails(label_id);

-- Composite index for pending Gmail sync query (most critical optimization)
CREATE INDEX IF NOT EXISTS idx_analyzed_emails_pending_sync 
ON analyzed_emails(user_id, status, applied_to_gmail, label_id, last_applied_label_id) 
WHERE status = 'labeled' AND label_id IS NOT NULL;

-- Custom Labels Indices
CREATE INDEX IF NOT EXISTS idx_custom_labels_user_id ON custom_labels(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_labels_label_name ON custom_labels(label_name);

-- Scan Cursor Indices
CREATE INDEX IF NOT EXISTS idx_scan_cursor_user_id ON scan_cursor(user_id);

-- URL Cache Indices
CREATE INDEX IF NOT EXISTS idx_url_cache_email_id ON url_cache(email_id);
CREATE INDEX IF NOT EXISTS idx_url_cache_url ON url_cache(url);
CREATE INDEX IF NOT EXISTS idx_url_cache_checked_at ON url_cache(checked_at);

-- Retry Queue Indices
CREATE INDEX IF NOT EXISTS idx_retry_queue_email_id ON retry_queue(email_id);
CREATE INDEX IF NOT EXISTS idx_retry_queue_retry_count_last_attempted_email_id
    ON retry_queue(retry_count, last_attempted, email_id);
