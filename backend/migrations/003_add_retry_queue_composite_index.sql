-- Task 2.7: retry queue composite index
-- Matches get_pending_retry_queue(): retry_count filter, last_attempted ordering,
-- and email_id join. The current schema scopes ownership through analyzed_emails.user_id.
CREATE INDEX IF NOT EXISTS idx_retry_queue_retry_count_last_attempted_email_id
    ON retry_queue (retry_count, last_attempted, email_id);
