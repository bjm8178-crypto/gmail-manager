"""
Phase 1 Task 2: Per-user job lock + in-flight email-id tracking
Prevents concurrent bulk/label-only/retry jobs for same user.
Prevents same email_id from being analyzed twice concurrently.
"""
import asyncio
from typing import Set, Dict, Optional
from logger_setup import get_logger

logger = get_logger(__name__)

# Per-user job locks: {user_id: asyncio.Lock}
_user_job_locks: Dict[int, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()  # Protects _user_job_locks dict

# In-flight email IDs: {user_id: Set[email_id]}
_inflight_emails: Dict[int, Set[str]] = {}
_inflight_lock = asyncio.Lock()  # Protects _inflight_emails dict


async def acquire_user_job_lock(user_id: int, timeout: float = 0.1) -> Optional[asyncio.Lock]:
    """
    Try to acquire the job lock for a user.
    Returns the lock if acquired, None if already locked (job in progress).
    
    Args:
        user_id: User ID
        timeout: How long to wait (seconds). Default 0.1 = fail fast for 409 response.
    
    Returns:
        asyncio.Lock if acquired, None if locked by another job
    """
    async with _locks_lock:
        if user_id not in _user_job_locks:
            _user_job_locks[user_id] = asyncio.Lock()
        lock = _user_job_locks[user_id]
    
    try:
        acquired = await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return lock if acquired else None
    except asyncio.TimeoutError:
        return None


def release_user_job_lock(lock: asyncio.Lock):
    """Release a previously acquired user job lock."""
    if lock.locked():
        lock.release()


# Per-user fetch locks: {user_id: asyncio.Lock}
_user_fetch_locks: Dict[int, asyncio.Lock] = {}
_fetch_locks_lock = asyncio.Lock()


async def acquire_user_fetch_lock(user_id: int, timeout: float = 0.1) -> Optional[asyncio.Lock]:
    """
    Try to acquire the fetch lock for a user.
    Prevents concurrent Gmail fetch operations for the same account.
    """
    async with _fetch_locks_lock:
        if user_id not in _user_fetch_locks:
            _user_fetch_locks[user_id] = asyncio.Lock()
        lock = _user_fetch_locks[user_id]

    try:
        acquired = await asyncio.wait_for(lock.acquire(), timeout=timeout)
        return lock if acquired else None
    except asyncio.TimeoutError:
        return None


def release_user_fetch_lock(lock: Optional[asyncio.Lock]):
    """Release a previously acquired user fetch lock."""
    if lock and lock.locked():
        lock.release()


async def register_inflight_email(user_id: int, email_id: str) -> bool:
    """
    Register an email as in-flight for analysis.
    Returns True if registered (was not already in-flight).
    Returns False if already in-flight (skip this email).
    """
    async with _inflight_lock:
        if user_id not in _inflight_emails:
            _inflight_emails[user_id] = set()
        
        if email_id in _inflight_emails[user_id]:
            return False  # Already in-flight
        
        _inflight_emails[user_id].add(email_id)
        return True


async def unregister_inflight_email(user_id: int, email_id: str):
    """Remove an email from in-flight tracking after analysis completes."""
    async with _inflight_lock:
        if user_id in _inflight_emails:
            _inflight_emails[user_id].discard(email_id)


async def clear_user_inflight_emails(user_id: int):
    """Clear all in-flight emails for a user (called at end of bulk job)."""
    async with _inflight_lock:
        if user_id in _inflight_emails:
            count = len(_inflight_emails[user_id])
            _inflight_emails[user_id].clear()
            logger.info(f"[JOB_LOCK] Cleared {count} in-flight email(s) for user {user_id}")


def get_job_lock_status() -> dict:
    """Return current lock and in-flight status for monitoring."""
    return {
        "active_jobs": sum(1 for lock in _user_job_locks.values() if lock.locked()),
        "total_users_tracked": len(_user_job_locks),
        "inflight_emails_by_user": {
            user_id: len(emails) 
            for user_id, emails in _inflight_emails.items() 
            if emails
        }
    }
