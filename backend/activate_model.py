"""
Phase 4/8: Model Activation Script
Activates a trained model version after manual review of metrics.
Includes atomic swap to prevent race conditions.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import sys
from database import _get_connection, _release_connection, _execute


def list_candidate_models():
    """List all trained models and their metrics."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(cursor, """
            SELECT 
                model_id, version, trained_at, training_row_count,
                validation_precision, validation_recall, 
                calibration_error, is_active
            FROM ml_models
            ORDER BY trained_at DESC
        """)
        
        rows = cursor.fetchall()
        
        logger.info("="*80)
        logger.info("AVAILABLE ML MODELS")
        logger.info("="*80)
        
        if not rows:
            logger.info("No models found. Run train_ml_model.py first.")
            return []
        
        for row in rows:
            model_id = row[0] if isinstance(row, tuple) else row['model_id']
            version = row[1] if isinstance(row, tuple) else row['version']
            trained_at = row[2] if isinstance(row, tuple) else row['trained_at']
            row_count = row[3] if isinstance(row, tuple) else row['training_row_count']
            precision = row[4] if isinstance(row, tuple) else row['validation_precision']
            recall = row[5] if isinstance(row, tuple) else row['validation_recall']
            cal_error = row[6] if isinstance(row, tuple) else row['calibration_error']
            is_active = row[7] if isinstance(row, tuple) else row['is_active']
            
            status = "ACTIVE" if is_active else "candidate"
            
            logger.info(f"\nModel ID: {model_id} [{status}]")
            logger.info(f"  Version: {version}")
            logger.info(f"  Trained: {trained_at}")
            logger.info(f"  Training rows: {row_count}")
            logger.info(f"  High-risk precision: {precision:.3f}")
            logger.info(f"  High-risk recall: {recall:.3f}")
            logger.info(f"  Calibration error: {cal_error:.4f}")
        
        logger.info("="*80)
        return rows
        
    finally:
        _release_connection(conn)


def activate_model(model_id: int):
    """
    Atomically activate a model by deactivating others first.
    Phase 4: Ensures only one model is active at a time (D4 mitigation).
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        _execute(cursor, """
            SELECT model_id, validation_recall, calibration_error
            FROM ml_models
            WHERE model_id = %s
        """, (model_id,))
        
        row = cursor.fetchone()
        if not row:
            logger.info(f"Error: Model ID {model_id} not found")
            return False
        
        recall = row[1] if isinstance(row, tuple) else row['validation_recall']
        cal_error = row[2] if isinstance(row, tuple) else row['calibration_error']
        
        MIN_RECALL = 0.90
        if recall < MIN_RECALL:
            logger.info(f"Error: Model does not meet minimum bar (recall {recall:.3f} < {MIN_RECALL})")
            logger.info("Cannot activate - retrain with more data or better features")
            return False
        
        _execute(cursor, "UPDATE ml_models SET is_active = 0")
        
        _execute(cursor, "UPDATE ml_models SET is_active = 1 WHERE model_id = %s", (model_id,))
        
        conn.commit()
        
        logger.info(f"\n✓ Model {model_id} activated successfully")
        logger.info(f"  Recall: {recall:.3f}, Calibration error: {cal_error:.4f}")
        logger.info("\nRestart the FastAPI server to load the new model.")
        
        return True
        
    except Exception as e:
        conn.rollback()
        logger.info(f"Error activating model: {e}")
        return False
    finally:
        _release_connection(conn)


def main():
    """Main activation workflow."""
    models = list_candidate_models()
    
    if not models:
        return 1
    
    if len(sys.argv) > 1:
        try:
            model_id = int(sys.argv[1])
            return 0 if activate_model(model_id) else 1
        except ValueError:
            logger.info("Error: Model ID must be an integer")
            return 1
    else:
        logger.info("\nUsage: python activate_model.py <model_id>")
        logger.info("Example: python activate_model.py 1")
        return 1


if __name__ == "__main__":
    exit(main())
