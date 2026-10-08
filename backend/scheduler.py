"""
Background task scheduler for Gmail Manager.

Schedules periodic maintenance tasks:
- Log cleanup (daily at 2am)
- Retry queue processing (hourly)
- ML model cache warming (every 6 hours)
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None
LOGS_DIR = Path(__file__).resolve().parent / "logs"

# Keep one scheduled pass bounded so a large backlog cannot monopolize the
# scheduler worker or unexpectedly fan out Gmail/AI work.
MAX_RETRY_BATCH_SIZE = 50
MAX_RETRY_USERS_PER_RUN = 1000


def _get_retry_user_ids() -> list[int]:
    """Return user IDs that have stored credentials, without exposing tokens."""
    from database import _execute, _get_connection, _release_connection

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        _execute(
            cursor,
            """
            SELECT user_id
            FROM users
            WHERE token IS NOT NULL
            ORDER BY user_id
            LIMIT %s
            """,
            (MAX_RETRY_USERS_PER_RUN,),
        )
        return [row["user_id"] for row in cursor.fetchall()]
    finally:
        _release_connection(conn)


def _run_retry_pipeline(user_id: int, user_email: str, email_ids: list[str]) -> None:
    """Consume the real async retry pipeline for one owned user's IDs."""
    from gmail import label_only_pipeline

    async def consume_pipeline() -> None:
        async for _event in label_only_pipeline(
            user_id=user_id,
            user_email=user_email,
            email_ids=email_ids,
        ):
            pass

    asyncio.run(consume_pipeline())


def cleanup_old_logs(retention_days: int = 90) -> None:
    """
    Remove log files older than retention_days.
    
    Args:
        retention_days: Number of days to retain logs (default: 90)
    """
    try:
        logs_dir = Path(LOGS_DIR)
        if not logs_dir.exists():
            logger.info(f"[SCHEDULER] Logs directory '{logs_dir}' does not exist, skipping cleanup")
            return
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for filename in os.listdir(logs_dir):
            if not filename.endswith('.log'):
                continue
            
            filepath = os.path.join(logs_dir, filename)
            
            # Skip if not a file
            if not os.path.isfile(filepath):
                continue
            
            # Check file modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_mtime < cutoff_date:
                os.remove(filepath)
                deleted_count += 1
                logger.info(f"[SCHEDULER] Deleted old log file: {filename} (modified: {file_mtime})")
        
        logger.info(f"[SCHEDULER] Log cleanup complete: deleted {deleted_count} files older than {retention_days} days")
    
    except Exception as e:
        logger.error(f"[SCHEDULER] Error during log cleanup: {e}", exc_info=True)


def process_retry_queue() -> None:
    """Retry bounded batches of failed analyses for each credentialed user."""
    try:
        from auth import get_credentials
        from database import (
            MAX_RETRIES,
            get_pending_retry_queue,
            get_user_email_by_id,
        )

        for user_id in _get_retry_user_ids():
            try:
                user_email = get_user_email_by_id(user_id)
                if not user_email or get_credentials(user_email) is None:
                    logger.info("[SCHEDULER] Skipping retry user without valid credentials")
                    continue

                retry_rows = get_pending_retry_queue(user_id, max_retries=MAX_RETRIES)
                retry_rows = retry_rows[:MAX_RETRY_BATCH_SIZE]
                email_ids = [row["email_id"] for row in retry_rows if row.get("email_id")]
                if not email_ids:
                    continue

                # The pipeline records a retry only when processing fails.
                # Pre-incrementing here would count one failed attempt twice.
                _run_retry_pipeline(user_id, user_email, email_ids)
                logger.info(
                    "[SCHEDULER] Retried %d failed emails for user_id=%s",
                    len(email_ids),
                    user_id,
                )
            except Exception as exc:
                # One user's token/data/pipeline failure must not prevent other
                # users' bounded retries from being attempted this pass.
                logger.error(
                    "[SCHEDULER] Retry failed for user_id=%s: %s",
                    user_id,
                    exc,
                    exc_info=True,
                )

    except Exception as e:
        logger.error(f"[SCHEDULER] Error processing retry queue: {e}", exc_info=True)


def warm_ml_model_cache() -> None:
    """
    Pre-load ML model into memory cache.

    Uses the canonical ML loader so model lookup, PostgreSQL connection
    management, hash verification, and cache population stay in one place.
    """
    try:
        logger.info("[SCHEDULER] Warming ML model cache")

        # Reuse the same loader used during application startup. It owns the
        # PostgreSQL connection lifecycle and updates ml_inference's cache.
        from ml_inference import load_active_model

        model = load_active_model()
        if model is None:
            logger.warning("[SCHEDULER] No active ML model found in database")
        else:
            logger.info("[SCHEDULER] Active ML model loaded into cache")

        logger.info("[SCHEDULER] ML model cache warming complete")

    except Exception as e:
        logger.error(f"[SCHEDULER] Error warming ML model cache: {e}", exc_info=True)


def start_scheduler() -> BackgroundScheduler:
    """
    Initialize and start the background scheduler with all scheduled jobs.
    
    Returns:
        BackgroundScheduler: The started scheduler instance
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[SCHEDULER] Scheduler already started, returning existing instance")
        return scheduler
    
    logger.info("[SCHEDULER] Initializing background scheduler")
    
    candidate = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            'coalesce': True,  # Combine missed runs into one
            'max_instances': 1,  # Only one instance of each job at a time
            'misfire_grace_time': 300  # 5 minutes grace period for missed jobs
        }
    )
    
    # Job 1: Daily log cleanup at 2am UTC
    candidate.add_job(
        func=cleanup_old_logs,
        trigger=CronTrigger(hour=2, minute=0),
        args=[90],  # retention_days=90
        id='cleanup_old_logs',
        name='Daily log cleanup',
        replace_existing=True
    )
    logger.info("[SCHEDULER] Scheduled job: cleanup_old_logs (daily at 2am UTC)")
    
    # Job 2: Hourly retry queue processing
    candidate.add_job(
        func=process_retry_queue,
        trigger=IntervalTrigger(hours=1),
        id='process_retry_queue',
        name='Hourly retry queue processing',
        replace_existing=True
    )
    logger.info("[SCHEDULER] Scheduled job: process_retry_queue (every hour)")
    
    # Job 3: ML model cache warming every 6 hours
    candidate.add_job(
        func=warm_ml_model_cache,
        trigger=IntervalTrigger(hours=6),
        id='warm_ml_model_cache',
        name='ML model cache warming',
        replace_existing=True
    )
    logger.info("[SCHEDULER] Scheduled job: warm_ml_model_cache (every 6 hours)")
    
    # Start the scheduler only after all jobs are registered. Keep the global
    # unset until start succeeds so a failed start can be retried cleanly.
    try:
        candidate.start()
    except Exception:
        if candidate.running:
            candidate.shutdown(wait=False)
        raise

    scheduler = candidate
    logger.info("[SCHEDULER] Background scheduler started successfully")

    return scheduler


def shutdown_scheduler() -> None:
    """
    Gracefully shut down the scheduler, waiting for running jobs to complete.
    """
    global scheduler
    
    if scheduler is None:
        logger.warning("[SCHEDULER] Scheduler not started, nothing to shut down")
        return
    
    logger.info("[SCHEDULER] Shutting down background scheduler...")
    
    try:
        scheduler.shutdown(wait=True)  # Wait for jobs to complete
        logger.info("[SCHEDULER] Scheduler shut down successfully")
        scheduler = None
    
    except Exception as e:
        logger.error(f"[SCHEDULER] Error shutting down scheduler: {e}", exc_info=True)


def get_scheduler_status() -> dict:
    """
    Get current scheduler status and job information.
    
    Returns:
        dict: Scheduler status including running state and job details
    """
    global scheduler
    
    if scheduler is None:
        return {
            "running": False,
            "jobs": []
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "running": scheduler.running,
        "jobs": jobs
    }
