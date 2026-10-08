"""
ML Training Readiness Check (Read-Only)
Reports whether sufficient high-risk training data exists to train the ML model.
Does NOT train anything, does NOT modify thresholds.
Used in Railway preDeployCommand to monitor progress toward training readiness.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

from database import _get_connection, _release_connection, _execute

# Match the thresholds from train_ml_model.py (do NOT modify these)
MIN_TRAINING_ROWS = 500
MIN_ROWS_PER_CLASS = 50


def check_readiness():
    """
    Check if we have sufficient data to train the ML model.
    Returns exit code 0 if ready, 1 if not ready.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        
        logger.info("=" * 70)
        logger.info("ML TRAINING READINESS CHECK")
        logger.info("=" * 70)
        
        # Total labeled rows
        _execute(cur, """
            SELECT COUNT(*) as total
            FROM analyzed_emails
            WHERE label_id IS NOT NULL AND scam_score IS NOT NULL
        """)
        row = cur.fetchone()
        total = row['total'] if isinstance(row, dict) else row[0]
        
        # Risk class distribution (using same thresholds as train_ml_model.py)
        _execute(cur, """
            SELECT 
                CASE 
                    WHEN scam_score >= 60 THEN 'high_risk'
                    ELSE 'low_risk'
                END as risk_class,
                COUNT(*) as count
            FROM analyzed_emails
            WHERE label_id IS NOT NULL AND scam_score IS NOT NULL
            GROUP BY risk_class
        """)
        
        class_counts = {}
        for row in cur.fetchall():
            risk_class = row['risk_class'] if isinstance(row, dict) else row[0]
            count = row['count'] if isinstance(row, dict) else row[1]
            class_counts[risk_class] = count
        
        high_risk_count = class_counts.get('high_risk', 0)
        low_risk_count = class_counts.get('low_risk', 0)
        
        logger.info(f"\nCurrent data status:")
        logger.info(f"  Total labeled rows: {total} (need {MIN_TRAINING_ROWS}+)")
        logger.info(f"  Low-risk rows:      {low_risk_count}")
        logger.info(f"  High-risk rows:     {high_risk_count} (need {MIN_ROWS_PER_CLASS}+)")
        
        logger.info("\n" + "-" * 70)
        
        # Check gates
        total_ready = total >= MIN_TRAINING_ROWS
        high_risk_ready = high_risk_count >= MIN_ROWS_PER_CLASS
        low_risk_ready = low_risk_count >= MIN_ROWS_PER_CLASS
        
        if total_ready and high_risk_ready and low_risk_ready:
            logger.info("STATUS: READY TO TRAIN")
            logger.info(f"\n  All thresholds met. You can now run:")
            logger.info(f"    python train_ml_model.py")
            logger.info("=" * 70)
            return 0
        
        else:
            logger.info("STATUS: NOT READY - Keep collecting data")
            logger.info("\n  Remaining requirements:")
            
            if not total_ready:
                remaining = MIN_TRAINING_ROWS - total
                logger.info(f"    - Need {remaining} more labeled emails (any risk level)")
            
            if not high_risk_ready:
                remaining = MIN_ROWS_PER_CLASS - high_risk_count
                logger.info(f"    - Need {remaining} more HIGH-RISK emails (scam_score >= 60)")
            
            if not low_risk_ready:
                remaining = MIN_ROWS_PER_CLASS - low_risk_count
                logger.info(f"    - Need {remaining} more LOW-RISK emails (scam_score < 60)")
            
            logger.info("\n  Continue running the AI cascade to accumulate training data.")
            logger.info("  This check will run automatically on each Railway deploy.")
            logger.info("=" * 70)
            return 1
        
    except Exception as e:
        logger.info(f"\nERROR: Readiness check failed: {e}")
        logger.info("=" * 70)
        return 2
    finally:
        _release_connection(conn)


if __name__ == "__main__":
    exit(check_readiness())
