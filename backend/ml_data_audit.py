"""
Phase 0: Data Audit Script
Checks analyzed_emails for class balance, row counts, and label quality.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

from database import _get_connection, _release_connection, _execute

def audit_data():
    conn = _get_connection()
    try:
        cur = conn.cursor()
        
        logger.info("=" * 60)
        logger.info("ML PIPELINE DATA AUDIT - Phase 0")
        logger.info("=" * 60)
        
        _execute(cur, "SELECT COUNT(*) as total FROM analyzed_emails")
        row = cur.fetchone()
        total = row['total'] if isinstance(row, dict) else row[0]
        logger.info(f"\nTotal analyzed emails: {total}")
        
        _execute(cur, """
            SELECT label_id, COUNT(*) as count 
            FROM analyzed_emails 
            GROUP BY label_id 
            ORDER BY count DESC
        """)
        logger.info("\nLabel distribution:")
        for row in cur.fetchall():
            label = (row['label_id'] if isinstance(row, dict) else row[0]) or "NULL"
            count = row['count'] if isinstance(row, dict) else row[1]
            pct = (count / total * 100) if total > 0 else 0
            logger.info(f"  Label {label}: {count} rows ({pct:.1f}%)")
        
        _execute(cur, """
            SELECT 
                CASE 
                    WHEN scam_score < 30 THEN 'low (0-30)'
                    WHEN scam_score < 60 THEN 'medium (30-60)'
                    ELSE 'high (60-100)'
                END as risk_bucket,
                COUNT(*) as count
            FROM analyzed_emails
            WHERE scam_score IS NOT NULL
            GROUP BY risk_bucket
            ORDER BY risk_bucket
        """)
        logger.info("\nScam score distribution:")
        for row in cur.fetchall():
            bucket = row['risk_bucket'] if isinstance(row, dict) else row[0]
            count = row['count'] if isinstance(row, dict) else row[1]
            logger.info(f"  {bucket}: {count} rows")
        
        _execute(cur, """
            SELECT COUNT(*) 
            FROM analyzed_emails 
            WHERE label_id IS NOT NULL AND scam_score IS NOT NULL
        """)
        row = cur.fetchone()
        labeled_count = row[0] if isinstance(row, tuple) else (row['count'] if 'count' in row else row[list(row.keys())[0]])
        logger.info(f"\nRows with both label_id and scam_score: {labeled_count}")
        
        logger.info("\n" + "=" * 60)
        logger.info("ASSESSMENT:")
        if total < 500:
            logger.info("INSUFFICIENT DATA: Need at least 500 rows total")
            logger.info("   Recommendation: Keep AI cascade running, delay ML implementation")
        elif labeled_count < 300:
            logger.info(f"LIMITED LABELED DATA: Only {labeled_count} fully labeled rows")
            logger.info("   Recommendation: Run in shadow mode only (Phase 5)")
        else:
            logger.info("OK - Sufficient data for initial training")
            logger.info("  Proceed with Phase 1 (schema changes)")
        logger.info("=" * 60)
        
    finally:
        _release_connection(conn)

if __name__ == "__main__":
    audit_data()
