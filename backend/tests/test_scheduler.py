"""
Tests for background scheduler functionality.

Tests scheduled jobs:
- cleanup_old_logs
- process_retry_queue
- warm_ml_model_cache
"""
import os
import sys
import time
from pathlib import Path
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

# Add backend directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import scheduler as scheduler_module
from scheduler import (
    cleanup_old_logs,
    process_retry_queue,
    warm_ml_model_cache,
    start_scheduler,
    shutdown_scheduler,
    get_scheduler_status
)


@pytest.fixture
def test_logs_dir(tmp_path, monkeypatch):
    """Create temporary logs directory for testing."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    monkeypatch.setattr(scheduler_module, "LOGS_DIR", logs_dir)
    return logs_dir


def test_cleanup_old_logs_uses_backend_relative_logs_directory():
    """Test cleanup path is anchored to the backend module, not the cwd."""
    assert scheduler_module.LOGS_DIR == Path(scheduler_module.__file__).resolve().parent / "logs"



def test_cleanup_old_logs_removes_old_files(test_logs_dir):
    """Test that cleanup_old_logs removes files older than retention period."""
    # Create test log files with different ages
    old_file = test_logs_dir / "old.log"
    recent_file = test_logs_dir / "recent.log"
    
    old_file.write_text("old log content")
    recent_file.write_text("recent log content")
    
    # Set old file modification time to 100 days ago
    old_mtime = (datetime.now() - timedelta(days=100)).timestamp()
    os.utime(old_file, (old_mtime, old_mtime))
    
    # Run cleanup with 90-day retention
    cleanup_old_logs(retention_days=90)
    
    # Verify old file deleted, recent file kept
    assert not old_file.exists()
    assert recent_file.exists()


def test_cleanup_old_logs_keeps_recent_files(test_logs_dir):
    """Test that cleanup_old_logs keeps files within retention period."""
    # Create recent log files
    file1 = test_logs_dir / "app.log"
    file2 = test_logs_dir / "app.log.1"
    
    file1.write_text("log content 1")
    file2.write_text("log content 2")
    
    # Run cleanup with 90-day retention
    cleanup_old_logs(retention_days=90)
    
    # Verify both files still exist
    assert file1.exists()
    assert file2.exists()


def test_cleanup_old_logs_handles_missing_directory():
    """Test that cleanup_old_logs handles missing logs directory gracefully."""
    # Should not raise exception
    cleanup_old_logs(retention_days=90)


def test_cleanup_old_logs_ignores_non_log_files(test_logs_dir):
    """Test that cleanup_old_logs only removes .log files."""
    # Create old files with different extensions
    old_log = test_logs_dir / "old.log"
    old_txt = test_logs_dir / "old.txt"
    old_json = test_logs_dir / "old.json"
    
    old_log.write_text("log")
    old_txt.write_text("txt")
    old_json.write_text("json")
    
    # Set all files to 100 days ago
    old_mtime = (datetime.now() - timedelta(days=100)).timestamp()
    for f in [old_log, old_txt, old_json]:
        os.utime(f, (old_mtime, old_mtime))
    
    # Run cleanup
    cleanup_old_logs(retention_days=90)
    
    # Verify only .log file deleted
    assert not old_log.exists()
    assert old_txt.exists()
    assert old_json.exists()


def test_process_retry_queue_retries_owned_pending_emails_with_exact_ids(monkeypatch):
    """Scheduled retries use each user's credentials and exact owned queue rows."""
    calls = []

    monkeypatch.setattr(scheduler_module, "_get_retry_user_ids", lambda: [7])
    monkeypatch.setattr("database.get_user_email_by_id", lambda user_id: "owner@example.com")
    monkeypatch.setattr("auth.get_credentials", lambda email: object())
    monkeypatch.setattr(
        "database.get_pending_retry_queue",
        lambda user_id, max_retries: [
            {"email_id": "owned-1", "retry_count": 1},
            {"email_id": "owned-2", "retry_count": 2},
        ],
    )
    monkeypatch.setattr("database.mark_retry_attempt", lambda *args: calls.append(("mark", args)))

    monkeypatch.setattr(
        scheduler_module,
        "_run_retry_pipeline",
        lambda user_id, user_email, email_ids: calls.append(
            ("pipeline", {"user_id": user_id, "user_email": user_email, "email_ids": email_ids})
        ),
    )

    process_retry_queue()

    assert calls == [
        (
            "pipeline",
            {
                "user_id": 7,
                "user_email": "owner@example.com",
                "email_ids": ["owned-1", "owned-2"],
            },
        ),
    ]


def test_process_retry_queue_enforces_batch_bound_and_skips_missing_credentials(monkeypatch):
    """Scheduled retries are bounded and never run without that user's credential."""
    seen = []

    monkeypatch.setattr(scheduler_module, "MAX_RETRY_BATCH_SIZE", 2)
    monkeypatch.setattr(scheduler_module, "_get_retry_user_ids", lambda: [7, 8])
    monkeypatch.setattr(
        "database.get_user_email_by_id",
        lambda user_id: {7: "owner@example.com", 8: "no-token@example.com"}[user_id],
    )
    monkeypatch.setattr(
        "auth.get_credentials",
        lambda email: object() if email == "owner@example.com" else None,
    )
    monkeypatch.setattr(
        "database.get_pending_retry_queue",
        lambda user_id, max_retries: [
            {"email_id": "one"},
            {"email_id": "two"},
            {"email_id": "three"},
        ],
    )
    monkeypatch.setattr("database.mark_retry_attempt", lambda *args: seen.append(("mark", args)))

    monkeypatch.setattr(
        scheduler_module,
        "_run_retry_pipeline",
        lambda user_id, user_email, email_ids: seen.append(("pipeline", user_id, email_ids)),
    )

    process_retry_queue()

    assert seen == [("pipeline", 7, ["one", "two"])]


def test_warm_ml_model_cache_loads_active_model():
    """Test that warming delegates to the canonical ML model loader."""
    with patch("ml_inference.load_active_model", return_value=object()) as load_model:
        warm_ml_model_cache()

    load_model.assert_called_once_with()


def test_warm_ml_model_cache_runs_without_error():
    """Test that warm_ml_model_cache executes without errors."""
    # Should not raise exception
    warm_ml_model_cache()


def test_start_scheduler_retries_after_failed_start():
    """A failed scheduler start must not poison the global retry path."""
    instances = []

    class FakeScheduler:
        def __init__(self, *args, **kwargs):
            self.running = False
            self.jobs = []
            self.fail_start = not instances
            instances.append(self)

        def add_job(self, **kwargs):
            self.jobs.append(kwargs)

        def start(self):
            if self.fail_start:
                raise RuntimeError("start failed")
            self.running = True

        def shutdown(self, wait=True):
            self.running = False

        def get_jobs(self):
            return []

    scheduler_module.scheduler = None
    with patch.object(scheduler_module, "BackgroundScheduler", FakeScheduler):
        with pytest.raises(RuntimeError, match="start failed"):
            start_scheduler()
        assert scheduler_module.scheduler is None

        retry = start_scheduler()
        assert retry is instances[1]
        assert retry.running is True

    shutdown_scheduler()
def test_start_scheduler_creates_instance():
    """Test that start_scheduler creates and starts scheduler."""
    try:
        scheduler = start_scheduler()
        
        # Verify scheduler is running
        assert scheduler is not None
        assert scheduler.running
        
        # Verify jobs are scheduled
        jobs = scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        
        assert 'cleanup_old_logs' in job_ids
        assert 'process_retry_queue' in job_ids
        assert 'warm_ml_model_cache' in job_ids
        
    finally:
        shutdown_scheduler()


def test_scheduler_status_when_running():
    """Test get_scheduler_status when scheduler is running."""
    try:
        start_scheduler()
        
        status = get_scheduler_status()
        
        assert status["running"] is True
        assert len(status["jobs"]) == 3
        
        # Verify job details
        job_ids = [job["id"] for job in status["jobs"]]
        assert 'cleanup_old_logs' in job_ids
        assert 'process_retry_queue' in job_ids
        assert 'warm_ml_model_cache' in job_ids
        
    finally:
        shutdown_scheduler()


def test_scheduler_status_when_stopped():
    """Test get_scheduler_status when scheduler is not running."""
    status = get_scheduler_status()
    
    assert status["running"] is False
    assert status["jobs"] == []


def test_shutdown_scheduler_gracefully():
    """Test that shutdown_scheduler stops the scheduler gracefully."""
    start_scheduler()
    
    # Verify running
    status = get_scheduler_status()
    assert status["running"] is True
    
    # Shutdown
    shutdown_scheduler()
    
    # Verify stopped
    status = get_scheduler_status()
    assert status["running"] is False


def test_start_scheduler_idempotent():
    """Test that calling start_scheduler multiple times returns same instance."""
    try:
        scheduler1 = start_scheduler()
        scheduler2 = start_scheduler()
        
        assert scheduler1 is scheduler2
        
    finally:
        shutdown_scheduler()


def test_shutdown_scheduler_when_not_started():
    """Test that shutdown_scheduler handles not-started case gracefully."""
    # Should not raise exception
    shutdown_scheduler()
