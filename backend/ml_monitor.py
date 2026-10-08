"""
Phase 9: ML Pipeline Monitoring Script
Tracks ML/AI agreement rate, drift detection, and model health.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

from datetime import datetime, timedelta
from database import _get_connection, _release_connection, _execute
from ml_inference import get_disagreement_rate


def monitor_ml_pipeline():
    """Generate ML pipeline health report."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        logger.info("="*80)
        logger.info("ML PIPELINE MONITORING REPORT")
        logger.info(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        # Active model info
        _execute(cursor, """
            SELECT version, trained_at, training_row_count, 
                   validation_precision, validation_recall, calibration_error
            FROM ml_models
            WHERE is_active = 1
        """)
        model_row = cursor.fetchone()
        
        if not model_row:
            logger.info("\n⚠ NO ACTIVE MODEL")
            logger.info("  Status: Running in AI-only mode")
            logger.info("  Action: Train and activate a model with train_ml_model.py + activate_model.py")
            return
        
        version = model_row[0] if isinstance(model_row, tuple) else model_row['version']
        trained_at = model_row[1] if isinstance(model_row, tuple) else model_row['trained_at']
        row_count = model_row[2] if isinstance(model_row, tuple) else model_row['training_row_count']
        precision = model_row[3] if isinstance(model_row, tuple) else model_row['validation_precision']
        recall = model_row[4] if isinstance(model_row, tuple) else model_row['validation_recall']
        cal_err = model_row[5] if isinstance(model_row, tuple) else model_row['calibration_error']
        
        logger.info("\n[ACTIVE MODEL]")
        logger.info(f"  Version: {version}")
        logger.info(f"  Trained: {trained_at}")
        logger.info(f"  Training rows: {row_count}")
        logger.info(f"  Validation precision: {precision:.3f}")
        logger.info(f"  Validation recall: {recall:.3f}")
        logger.info(f"  Calibration error: {cal_err:.4f}")
        
        # Prediction distribution (last 7 days)
        _execute(cursor, """
            SELECT source, COUNT(*) as count
            FROM analyzed_emails
            WHERE analyzed_at >= datetime('now', '-7 days')
            GROUP BY source
        """)
        
        logger.info("\n[PREDICTION SOURCES - Last 7 days]")
        source_counts = {}
        total = 0
        for row in cursor.fetchall():
            source = row[0] if isinstance(row, tuple) else row['source']
            count = row[1] if isinstance(row, tuple) else row['count']
            source_counts[source] = count
            total += count
        
        if total == 0:
            logger.info("  No emails analyzed in last 7 days")
        else:
            for source in ['ml', 'ai', 'ml_audit_escalated']:
                count = source_counts.get(source, 0)
                pct = (count / total * 100) if total > 0 else 0
                logger.info(f"  {source:20s}: {count:5d} ({pct:5.1f}%)")
        
        # Disagreement rate monitoring (drift detection)
        for days in [1, 7, 30]:
            rate = get_disagreement_rate(days)
            logger.info(f"\n[DISAGREEMENT RATE - Last {days} days]")
            logger.info(f"  Rate: {rate:.1%}")
            
            if rate > 0.25:
                logger.info(f"  ⚠ WARNING: High disagreement rate (>{25:.0%})")
                logger.info("  Action: Review recent disagreements and consider retraining")
            elif rate > 0.15:
                logger.info(f"  ⚠ CAUTION: Elevated disagreement rate (>{15:.0%})")
                logger.info("  Action: Monitor closely, retrain if trend continues")
            else:
                logger.info("  ✓ Normal range")
        
        # Recent disagreements
        _execute(cursor, """
            SELECT 
                d.email_id, d.ml_prediction, d.ml_confidence, 
                d.ai_prediction, d.agreed, d.logged_at,
                e.subject
            FROM ml_disagreements d
            JOIN analyzed_emails e ON d.email_id = e.email_id
            WHERE d.logged_at >= datetime('now', '-3 days')
              AND d.agreed = 0
            ORDER BY d.logged_at DESC
            LIMIT 10
        """)
        
        disagreement_rows = cursor.fetchall()
        if disagreement_rows:
            logger.info("\n[RECENT DISAGREEMENTS - Last 3 days]")
            logger.info("  (Showing up to 10 most recent)")
            for row in disagreement_rows:
                email_id = (row[0] if isinstance(row, tuple) else row['email_id'])[:12]
                ml_pred = row[1] if isinstance(row, tuple) else row['ml_prediction']
                ml_conf = row[2] if isinstance(row, tuple) else row['ml_confidence']
                ai_pred = row[3] if isinstance(row, tuple) else row['ai_prediction']
                logged_at = row[5] if isinstance(row, tuple) else row['logged_at']
                subject = (row[6] if isinstance(row, tuple) else row['subject'])[:40]
                
                logger.info(f"\n  Email: {email_id}... | {logged_at}")
                logger.info(f"    Subject: {subject}")
                logger.info(f"    ML: {ml_pred} (conf={ml_conf:.3f})")
                logger.info(f"    AI: {ai_pred}")
        
        # ML confidence distribution
        _execute(cursor, """
            SELECT 
                CASE 
                    WHEN ml_confidence >= 0.95 THEN 'very_high (0.95+)'
                    WHEN ml_confidence >= 0.85 THEN 'high (0.85-0.95)'
                    WHEN ml_confidence >= 0.70 THEN 'medium (0.70-0.85)'
                    ELSE 'low (<0.70)'
                END as conf_bucket,
                COUNT(*) as count
            FROM analyzed_emails
            WHERE source = 'ml' 
              AND ml_confidence IS NOT NULL
              AND analyzed_at >= datetime('now', '-7 days')
            GROUP BY conf_bucket
        """)
        
        logger.info("\n[ML CONFIDENCE DISTRIBUTION - Last 7 days]")
        for row in cursor.fetchall():
            bucket = row[0] if isinstance(row, tuple) else row['conf_bucket']
            count = row[1] if isinstance(row, tuple) else row['count']
            logger.info(f"  {bucket:25s}: {count:5d}")
        
        logger.info("\n" + "="*80)
        logger.info("Report complete")
        logger.info("="*80)
        
    finally:
        _release_connection(conn)


if __name__ == "__main__":
    monitor_ml_pipeline()
