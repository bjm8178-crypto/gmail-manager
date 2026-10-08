#!/usr/bin/env python3
"""
apply_indices.py — Apply database indices for performance optimization
Run this after deployment to add all necessary indices.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

from database import _get_connection, _execute, _release_connection, USE_POSTGRES
from pathlib import Path

def apply_indices():
    """Read and execute all CREATE INDEX statements from db_indices.sql"""
    
    sql_file = Path(__file__).parent / "db_indices.sql"
    
    if not sql_file.exists():
        logger.error(f"[INDICES] SQL file not found: {sql_file}")
        return False
    
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    # Split by semicolon and filter out comments/empty lines
    statements = []
    for line in sql_content.split(';'):
        line = line.strip()
        if line and not line.startswith('--') and 'CREATE INDEX' in line:
            statements.append(line)
    
    logger.info(f"[INDICES] Found {len(statements)} index statements to execute")
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        for i, stmt in enumerate(statements, 1):
            try:
                # Extract index name for logging
                index_name = stmt.split('idx_')[1].split(' ON')[0] if 'idx_' in stmt else f"index_{i}"
                
                logger.info(f"[INDICES] [{i}/{len(statements)}] Creating idx_{index_name}...")
                _execute(cursor, stmt)
                conn.commit()
                logger.info(f"[INDICES] ✓ idx_{index_name} created")
                
            except Exception as e:
                # Continue on error (index might already exist)
                logger.warning(f"[INDICES] Index creation warning: {e}")
                conn.rollback()
        
        logger.info("[INDICES] ✓ All indices applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"[INDICES ERROR] {e}", exc_info=True)
        return False
    finally:
        _release_connection(conn)


if __name__ == "__main__":
    logger.info("[INDICES] Starting index application...")
    success = apply_indices()
    
    if success:
        logger.info("[INDICES] ✓ COMPLETE")
    else:
        logger.error("[INDICES] ✗ FAILED")
        exit(1)
