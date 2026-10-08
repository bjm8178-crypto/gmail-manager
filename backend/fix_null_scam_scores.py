"""
fix_null_scam_scores.py — One-time migration to fix NULL scam_scores

This script updates any emails with NULL scam_score to 0.
Run this once after deploying the fix.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
from database import _get_connection

def fix_null_scam_scores():
    """Update all NULL scam_scores to 0."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Check how many NULL scam_scores exist
        cursor.execute("SELECT COUNT(*) FROM analyzed_emails WHERE scam_score IS NULL")
        count = cursor.fetchone()[0]
        
        logger.info(f"[MIGRATION] Found {count} emails with NULL scam_score")
        
        if count > 0:
            # Update NULL scam_scores to 0
            cursor.execute("UPDATE analyzed_emails SET scam_score = 0 WHERE scam_score IS NULL")
            conn.commit()
            logger.info(f"[MIGRATION] Updated {count} emails: scam_score NULL → 0")
        else:
            logger.info("[MIGRATION] No NULL scam_scores found. Database is clean.")
        
    except Exception as e:
        conn.rollback()
        logger.info(f"[MIGRATION] ERROR: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("[MIGRATION] Starting NULL scam_score fix...")
    fix_null_scam_scores()
    logger.info("[MIGRATION] Migration complete!")
