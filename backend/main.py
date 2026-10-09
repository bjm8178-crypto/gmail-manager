"""
main.py — FastAPI Backend Entry Point (Restructured)
Runs on port 8000. Provides OAuth endpoints, email fetching, AI analysis,
security scanning, scam alerts, and email rewriting.
Uses SessionMiddleware to store user_id and gmail_address after login.
"""

import os
import sys
import json
import webbrowser
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load the backend-local environment first; the repository-level file is only a
# fallback. Modules imported below snapshot database configuration at import
# time, so this order must remain before the custom imports.
_BACKEND_ROOT = Path(__file__).resolve().parent
load_dotenv(_BACKEND_ROOT / ".env", override=False)
load_dotenv(_BACKEND_ROOT.parent / ".env", override=False)

from logger_setup import get_logger
logger = get_logger(__name__)

# Force UTF-8 encoding for stdout/stderr to handle emoji in logs
if sys.platform == 'win32':
    import io
    # Do not replace captured streams at import time; pytest and ASGI servers own them.
    # Do not replace captured streams at import time; pytest and ASGI servers own them.

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import our custom modules
from auth import get_auth_url, consume_oauth_state, handle_callback, is_logged_in, get_credentials, delete_token, get_user_email, migrate_legacy_tokens
from gmail import fetch_emails, analyze_bulk_ordered, trash_email, delete_email, send_reply
from database import (
    init_db, get_analyzed_emails,
    get_labels, add_label, delete_label,
    reset_database, mark_email_safe,
    get_delete_mode, set_delete_mode,
    MAX_RETRIES,
    USE_POSTGRES,
    update_analyzed_email, get_label_id_by_name,
    get_user_email_by_id,
    _get_connection, _execute, _release_connection,
)
from ml_inference import load_active_model
from ai_router import ai_router, REWRITE_PROMPT, CLASSIFICATION_PROMPT, get_provider_status
from dependencies import require_auth
from jwt_auth import create_access_token, get_user_from_token
from cache_manager import get_cache_stats, invalidate_user_cache
from api_compression import GZipMiddleware
from csrf import CSRFMiddleware, generate_csrf_token
from security_headers import SecurityHeadersMiddleware
from scheduler import start_scheduler, shutdown_scheduler, get_scheduler_status
from schemas import (
    UpdateEmailLabelRequest,
    BatchLabelUpdateRequest,
    BulkLabelRequest,
    CreateLabelRequest,
    UpdateDeleteModeRequest,
    BatchDeleteRequest,
    BulkDeleteRequest,
    BulkMarkSafeRequest,
    BulkQuarantineRequest,
    AIRewriteRequest,
    ReanalyzeRequest,
)

# ---------- APP INITIALIZATION ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # ---------- STARTUP ----------
    logger.info("[STARTUP] BEGIN - Railway deployment 2026-08-20T04:05Z")
    
    # Set explicit thread pool size for asyncio.to_thread() to prevent exhaustion
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=32))
    logger.info("[SERVER] Configured asyncio executor with 32 worker threads")
    
    logger.info("[STARTUP] Calling init_db()...")
    init_db()
    logger.info("[STARTUP] init_db() complete")
    
    # Load active ML model if available
    logger.info("[STARTUP] Calling load_active_model()...")
    try:
        load_active_model()
        logger.info("[STARTUP] load_active_model() complete")
    except Exception as e:
        logger.error(f"[STARTUP ERROR] load_active_model() failed: {e}", exc_info=True)
    
    # Import legacy file-based tokens into the DB (no-op on ephemeral hosts with no files)
    try:
        migrate_legacy_tokens()
    except Exception as e:
        logger.info(f"[SERVER] Token migration skipped: {e}")
    
    # Optional scheduler (off for free sleeping hosts).
    if os.getenv("ENABLE_SCHEDULER", "false").strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("[STARTUP] Starting background scheduler...")
        try:
            start_scheduler()
            logger.info("[STARTUP] Background scheduler started successfully")
        except Exception as e:
            logger.error(f"[STARTUP ERROR] Failed to start scheduler: {e}", exc_info=True)
    else:
        logger.info("[STARTUP] Background scheduler disabled by configuration")
    
    # Apply database indices for performance
    logger.info("[STARTUP] Applying database indices...")
    try:
        from apply_indices import apply_indices
        apply_indices()
    except Exception as e:
        logger.warning(f"[STARTUP] Index application skipped: {e}")
    
    logger.info("[STARTUP] COMPLETE - Gmail Manager API ready on port 8000")
    
    yield
    
    # ---------- SHUTDOWN ----------
    logger.info("[SHUTDOWN] BEGIN - Shutting down Gmail Manager API")
    
    # Stop background scheduler
    try:
        shutdown_scheduler()
        logger.info("[SHUTDOWN] Background scheduler stopped successfully")
    except Exception as e:
        logger.error(f"[SHUTDOWN ERROR] Failed to stop scheduler: {e}", exc_info=True)
    
    logger.info("[SHUTDOWN] COMPLETE - Gmail Manager API shut down gracefully")


app = FastAPI(
    title="Gmail Manager API",
    description="Backend API for Gmail Manager desktop application",
    version="2.0.0",
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Session middleware for storing user_id after login
# Configure session cookies to work across domains (Vercel frontend → Railway backend)
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET_KEY env var is required. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="gmail_manager_session",
    max_age=86400 * 7,  # 7 days
    same_site="none",  # Allow cross-site cookies (Vercel → Railway)
    https_only=True,  # Require HTTPS in production
)

# Reject state-changing requests without a matching CSRF cookie/header.
app.add_middleware(CSRFMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS - Fixed for credentials mode
# Wildcard (*) not allowed with credentials, must specify exact origins
# Check multiple Railway environment indicators
IS_PRODUCTION = (
    os.getenv("RAILWAY_ENVIRONMENT") is not None or 
    os.getenv("RAILWAY_PROJECT_ID") is not None or
    os.getenv("PORT") is not None  # Railway sets PORT env var
)

if IS_PRODUCTION:
    # Production: Specific Vercel origin (required for credentials: 'include')
    origins = [
        "https://gmail-manager-gamma.vercel.app",
        "https://gmail-manager-gamma.vercel.app/",  # With trailing slash
        "http://localhost:5173",  # Allow local dev testing against prod backend
        "http://localhost:3000",
        "http://localhost:5174",
    ]
    # Add dynamic allowed origin from env if present
    env_origin = os.getenv("ALLOWED_ORIGIN")
    if env_origin:
        origins.extend([env_origin, env_origin + "/"])
        logger.info(f"[CORS] Added ALLOWED_ORIGIN from env: {env_origin}")
    logger.info(f"[CORS] Production mode - Allowed origins: {origins}")
else:
    # Local dev: Specific localhost origins
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5174",
        "https://gmail-manager-gamma.vercel.app",  # Allow testing prod frontend
    ]
    logger.info(f"[CORS] Dev mode - Allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1024, compression_level=6)


# ---------- HELPER: Get user_id from session ----------

def _get_user_id(request: Request) -> int | None:
    """Extract user_id from the session. Returns None if not logged in."""
    return request.session.get("user_id")


def _request_user_email(request: Request) -> str | None:
    """Extract the authenticated user's email from JWT or session."""
    user_data = get_user_from_token(request)
    if user_data and user_data.get("email"):
        return user_data["email"]
    return request.session.get("gmail_address")


def _is_authenticated(request: Request) -> bool:
    """Return True when the request has a valid JWT or session auth for a known user."""
    user_email = _request_user_email(request)
    if not user_email:
        return False
    return is_logged_in(user_email)


def _require_user_id(request: Request) -> int:
    """
    Extract user_id from JWT/session, raising an error if not found.
    Falls back to fetching from database if session is empty but user is logged in.
    """
    user_data = get_user_from_token(request)
    if user_data and user_data.get("user_id"):
        user_id = user_data["user_id"]
        request.session["user_id"] = user_id
        if user_data.get("email"):
            request.session["gmail_address"] = user_data["email"]
        return user_id

    user_id = request.session.get("user_id")
    if user_id:
        return user_id

    # Fallback: if user is logged in (has valid token) but session lost,
    # re-derive user_id from their email
    user_email = _request_user_email(request)
    if is_logged_in(user_email):
        email = user_email
        if email:
            from database import get_user_id, upsert_user, seed_default_labels
            try:
                user_id = get_user_id(email)
            except ValueError:
                # User exists in token but not in DB (pre-restructuring token)
                # Auto-upsert them
                creds = get_credentials(user_email)
                access_token = creds.token if creds else ""
                user_id = upsert_user(email, access_token)
                seed_default_labels(user_id)
            # Restore session
            request.session["user_id"] = user_id
            request.session["gmail_address"] = email
            return user_id

    return None


PENDING_GMAIL_SYNC_CONDITION = """
          AND status = 'labeled'
          AND label_id IS NOT NULL
          AND (
              applied_to_gmail = 0
              OR applied_to_gmail IS NULL
              OR last_applied_label_id IS NULL
              OR last_applied_label_id <> label_id
          )
"""

# ---------- AUTH ENDPOINTS ----------

@app.get("/auth/login")
@limiter.limit("5/minute")
async def auth_login(request: Request):
    """GET /auth/login — Opens Google OAuth in browser."""
    auth_url = get_auth_url(request.session)
    return {"auth_url": auth_url, "message": "Opening Google login in browser..."}


@app.get("/auth/callback")
@limiter.limit("10/minute")
async def auth_callback(request: Request):
    """
    GET /auth/callback
    Google redirects here after user grants permissions.
    Generates JWT token for cross-domain authentication.
    Stores the user's OAuth token in the database (keyed by gmail_address).
    """
    try:
        logger.info(f"[AUTH CALLBACK] Received callback request")
        code = request.query_params.get("code")
        
        if not code:
            logger.error("[AUTH CALLBACK ERROR] No authorization code in request")
            return JSONResponse(
                status_code=400,
                content={"error": "No authorization code received from Google"},
            )
        
        logger.info(f"[AUTH CALLBACK] Processing authorization code (length: {len(code)})")
        verifier = consume_oauth_state(request.query_params.get("state"), request.session)
        if not verifier:
            return JSONResponse(status_code=400, content={"error": "Invalid or expired OAuth state. Restart login."})
        result = handle_callback(code, code_verifier=verifier)
        logger.info(f"[AUTH CALLBACK] handle_callback result: {result}")
        
        # Store user_id and gmail_address in session (for backward compatibility)
        if result.get("success") and result.get("user_id"):
            user_id = result["user_id"]
            user_email = result["gmail_address"]
            
            logger.info(f"[AUTH CALLBACK] Setting session for user_id={user_id}, email={user_email}")
            request.session["user_id"] = user_id
            request.session["gmail_address"] = user_email

            # Generate JWT token for cross-domain authentication
            logger.info("[AUTH CALLBACK] Creating JWT token")
            jwt_token = create_access_token(user_id, user_email)
            logger.info("[AUTH CALLBACK] JWT token created")

            logger.info(f"[AUTH CALLBACK] Session set: user_id={user_id}, email={user_email}")
            
            # Phase 6: Audit log successful login
            from audit import log_event, ACTION_LOGIN, SEVERITY_INFO
            log_event(
                user_id=user_id,
                action=ACTION_LOGIN,
                severity=SEVERITY_INFO,
                metadata={"email": user_email, "success": True},
                request=request
            )
            
            # Redirect without exposing the JWT in the URL or response body.
            # Local development must return to the local Vite app; production
            # keeps the deployed frontend unless FRONTEND_URL overrides it.
            frontend_url = os.getenv("FRONTEND_URL")
            if not frontend_url:
                frontend_url = (
                    "https://gmail-manager-gamma.vercel.app"
                    if IS_PRODUCTION
                    else "http://localhost:5173"
                )
            frontend_url = frontend_url.rstrip("/")
            redirect = RedirectResponse(url=f"{frontend_url}/inbox", status_code=303)
            
            # In local dev (http://), Secure flag prevents cookie delivery.
            # In production (https://), always use Secure.
            use_secure = IS_PRODUCTION
            
            redirect.set_cookie(
                key="jwt_token",
                value=jwt_token,
                max_age=604800,
                httponly=True,
                secure=use_secure,
                samesite="lax",
                path="/",
            )
            redirect.set_cookie(
                key="csrf_token",
                value=generate_csrf_token(),
                max_age=604800,
                httponly=False,
                secure=use_secure,
                samesite="lax",
                path="/",
            )
            logger.info(f"[AUTH CALLBACK] Set cookies with secure={use_secure}, redirecting to {frontend_url}/inbox")
            redirect.headers["Cache-Control"] = "no-store"
            redirect.headers["Referrer-Policy"] = "no-referrer"
            return redirect

        
        # If authentication failed
        logger.error(f"[AUTH CALLBACK ERROR] Authentication failed: {result.get('message', 'Unknown error')}")
        
        # Phase 6: Audit log failed login attempt
        from audit import log_event, ACTION_LOGIN_FAILED, SEVERITY_WARNING
        log_event(
            user_id=None,  # No user_id for failed login
            action=ACTION_LOGIN_FAILED,
            severity=SEVERITY_WARNING,
            metadata={"reason": result.get("message", "Unknown error")},
            request=request
        )
        
        return JSONResponse(
            status_code=401,
            content={"error": result.get("message", "Authentication failed")}
        )
    
    except Exception as e:
        logger.error(f"[AUTH CALLBACK EXCEPTION] {type(e).__name__}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Authentication failed due to an internal server error."}
        )


@app.get("/ml/status")
async def ml_status():
    '''GET /ml/status - Check if ML model is loaded'''
    from ml_inference import is_model_available, _MODEL_VERSION
    return {
        'model_loaded': is_model_available(),
        'model_version': _MODEL_VERSION,
        'timestamp': '2026-08-20T03:57:00Z'
    }

@app.get("/auth/status")
async def auth_status(request: Request):
    """GET /auth/status — Returns login status and user email."""
    # Never log Authorization headers or complete session contents.
    user_data = get_user_from_token(request)
    
    response_data = None
    has_csrf_cookie = "csrf_token" in request.cookies

    if user_data:
        # User authenticated via JWT token
        user_email = user_data["email"]
        user_id = user_data["user_id"]
        logger.info("[AUTH/STATUS] JWT authentication successful")
        
        # Verify the Gmail token is still valid
        logged_in = is_logged_in(user_email)
        
        if logged_in:
            response_data = {
                "logged_in": True,
                "email": user_email,
                "user_id": user_id
            }
    
    # Fallback to session authentication (for backward compatibility)
    if not response_data:
        user_email = request.session.get("gmail_address")
        user_id = request.session.get("user_id")
        
        logger.info("[AUTH/STATUS] Session authentication checked")
        
        if user_email:
            # User has active session, check if token is valid
            logged_in = is_logged_in(user_email)
            logger.info(f"[AUTH/STATUS] Stored token valid: {logged_in}")
        else:
            # No session, check stored token for the session user
            logged_in = is_logged_in(user_email)
            logger.info(f"[AUTH/STATUS DEBUG] Token check: {logged_in}")
        
        response_data = {"logged_in": logged_in}
        if logged_in:
            email = user_email or get_user_email(user_email)
            if email:
                response_data["email"] = email
    
    logger.info(f"[AUTH/STATUS DEBUG] Returning: {response_data}")
    
    # If user is authenticated but missing csrf_token cookie, set one now
    if response_data.get("logged_in") and not has_csrf_cookie:
        from csrf import generate_csrf_token
        response = JSONResponse(content=response_data)
        csrf_value = generate_csrf_token()
        response.set_cookie(
            key="csrf_token",
            value=csrf_value,
            max_age=604800,
            httponly=False,
            secure=IS_PRODUCTION,
            samesite="lax",
            path="/",
        )
        logger.info(f"[AUTH/STATUS] Set csrf_token cookie (secure={IS_PRODUCTION})")
        return response
    
    return response_data


@app.post("/auth/logout")
async def auth_logout(request: Request):
    """POST /auth/logout — Deletes the stored token and clears session."""
    # Try to get user email from JWT first, then session
    user_email = None
    user_data = get_user_from_token(request)
    if user_data and user_data.get("email"):
        user_email = user_data["email"]
    else:
        user_email = request.session.get("gmail_address")
    
    # Delete user-specific token if we have the email
    if user_email:
        try:
            from auth import delete_token as delete_user_token
            delete_user_token(user_email)
            logger.info(f"[AUTH] Deleted user-specific token for {user_email}")
        except Exception as e:
            logger.info(f"[AUTH] Error deleting user token: {e}")
    
    # Clear session and both authentication cookies.
    request.session.clear()
    response = JSONResponse({"logged_in": False, "message": "Logged out successfully"})
    response.delete_cookie("jwt_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return response


# ---------- EMAIL ENDPOINTS ----------

@app.get("/emails/fetch")
async def emails_fetch(request: Request, user: dict = Depends(require_auth), limit: int = 50, page_token: str = None):
    """GET /emails/fetch — Fetches emails from Gmail."""

    result = fetch_emails(limit=limit, page_token=page_token, user_email=_request_user_email(request))
    return {
        "emails": result["emails"],
        "next_page_token": result["next_page_token"],
        "count": len(result["emails"]),
    }


@app.get("/emails")
async def emails_get(request: Request, user: dict = Depends(require_auth)):
    """GET /emails — Returns all cached analyzed emails from SQLite."""
    try:
        logger.info("[EMAILS-GET] Request received")
        user_id = user["user_id"]

        logger.info(f"[EMAILS-GET] Fetching emails for user_id={user_id}")
        emails = get_analyzed_emails(user_id)
        logger.info(f"[EMAILS-GET] Found {len(emails)} emails")
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        logger.error(f"[EMAILS-GET ERROR] {type(e).__name__}: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to fetch emails. Please try again."})


@app.get("/emails/analyzed")
async def emails_analyzed(request: Request, user: dict = Depends(require_auth)):
    """GET /emails/analyzed — Alias for GET /emails for backward compatibility."""
    user_id = user["user_id"]

    emails = get_analyzed_emails(user_id)
    return {"emails": emails, "count": len(emails)}


# ---------- BULK ANALYSIS ENDPOINT WITH SSE ----------

@app.post("/emails/analyze-bulk")
@limiter.limit("3/hour")
async def emails_analyze_bulk(request: Request, user: dict = Depends(require_auth), count: int = 50):
    """
    POST /emails/analyze-bulk?count=50
    Runs the AI-only bulk analysis pipeline.
    Streams results back as Server-Sent Events (SSE).
    count: Number of emails to analyze (1-500)
    """

    limit = min(max(count, 1), 500)  # clamp to prevent AI/Gmail quota exhaustion
    user_id = user["user_id"]


    # Item 1: Block analysis if user has zero labels
    user_labels = get_labels(user_id)
    if not user_labels:
        return JSONResponse(
            status_code=400,
            content={"error": "no_labels", "message": "You must create at least one label before running analysis. Go to Settings to add labels."}
        )

    from starlette.responses import StreamingResponse

    async def sse_stream():
        async for event in analyze_bulk_ordered(limit=limit, user_id=user_id):
            event_type = event.get("type", "message")
            if event_type == "email_done":
                event_type = "progress"
            event_data = json.dumps(event)
            yield f"event: {event_type}\ndata: {event_data}\n\n"

    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/emails/fetch-only")
async def emails_fetch_only(request: Request, user: dict = Depends(require_auth), limit: int = 50):
    """POST /emails/fetch-only - Fetch emails from Gmail, save as status='fetched' (no AI)"""
    user_id = user["user_id"]

    
    from gmail import fetch_only_pipeline
    
    final_event = {"fetched": 0, "skipped": 0}
    async for event in fetch_only_pipeline(limit=limit, user_id=user_id):
        final_event = event
    
    return JSONResponse(content=final_event)


@app.post("/emails/label-only")
async def emails_label_only(request: Request, user: dict = Depends(require_auth), limit: int = None):
    """POST /emails/label-only - Run AI analysis on status='fetched' emails"""
    user_id = user["user_id"]

    
    user_labels = get_labels(user_id)
    if not user_labels:
        return JSONResponse(status_code=400, content={"error": "no_labels"})
    
    from gmail import label_only_pipeline
    
    final_event = {"analyzed": 0, "failed": 0}
    async for event in label_only_pipeline(limit=limit, user_id=user_id):
        final_event = event
    
    return JSONResponse(content=final_event)



def _apply_label_change(email_id: str, new_label_name: str, user_id: int, user_email: str) -> dict:
    """
    Internal function: Apply label change to a single email.
    Updates database and Gmail atomically, with rollback on Gmail failure.
    Returns dict with 'success': bool, 'error': str (if failed).
    Does NOT touch scam_score, scam_indicators, or is_quarantined.
    
    Args:
        user_email: Gmail address (each thread builds its own service object for thread safety)
    """
    from database import get_labels, get_analyzed_emails, update_email_label_id
    from gmail import get_or_create_label, change_label, get_gmail_service

    try:
        # Validate new label exists
        labels = get_labels(user_id)
        new_label = next((l for l in labels if l["label_name"] == new_label_name), None)
        if not new_label:
            return {"success": False, "error": "Label not found"}

        # Get current email state
        emails = get_analyzed_emails(user_id)
        email = next((e for e in emails if e["email_id"] == email_id), None)
        if not email:
            return {"success": False, "error": "Email not found"}

        old_label_id = email.get("label_id")
        old_label = next((l for l in labels if l["label_id"] == old_label_id), None) if old_label_id else None

        # Update database
        try:
            update_email_label_id(email_id, new_label["label_id"], user_id=user_id)
        except Exception as e:
            return {"success": False, "error": f"db_error: {e}"}

        # Update Gmail
        service = get_gmail_service(user_email)
        if not service:
            # Rollback database change
            if old_label_id:
                update_email_label_id(email_id, old_label_id, user_id=user_id)
            return {"success": False, "error": "gmail_not_authenticated"}

        try:
            # Build Gmail labels cache from actual Gmail labels (prevents 409 conflicts)
            gmail_labels_result = service.users().labels().list(userId="me").execute()
            gmail_labels_cache = {
                lbl["name"]: lbl["id"] for lbl in gmail_labels_result.get("labels", [])
            }
            
            old_gmail_label_id = None
            if old_label:
                old_gmail_label_id = get_or_create_label(user_email, old_label["label_name"], user_id, gmail_labels_cache)

            new_gmail_label_id = get_or_create_label(user_email, new_label_name, user_id, gmail_labels_cache)
            if not new_gmail_label_id:
                raise Exception("Failed to get/create Gmail label")

            # Change label in Gmail (remove old, add new)
            change_label(user_email, email_id, old_gmail_label_id, new_gmail_label_id)

        except Exception as e:
            # Rollback database change
            if old_label_id:
                update_email_label_id(email_id, old_label_id, user_id=user_id)
            else:
                # If there was no old label, we can't fully rollback - log error
                logger.error(f"[ERROR] Gmail label change failed, but can't rollback to NULL label: {e}")
            return {"success": False, "error": f"gmail_api_error: {e}"}

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": f"unexpected_error: {e}"}


def _sync_label_to_gmail(email_id: str, user_id: int, user_email: str, gmail_labels_cache: dict[str, str]) -> dict:
    """
    Sync email's current label_id to Gmail, removing old label if needed.

    Reads current label_id and last_applied_label_id from DB:
    - If last_applied_label_id is NULL: first-ever apply, just add new label
    - If last_applied_label_id differs from current label_id: remove old + add new
    - If same: no-op (already synced)

    On success: updates both applied_to_gmail=1 AND last_applied_label_id=<current label_id>

    Args:
        user_email: Gmail address (each thread builds its own service object for thread safety)
        gmail_labels_cache: Pre-built dict mapping label names to Gmail label IDs (shared across batch)

    Returns dict with 'success': bool, 'error': str (if failed).
    Does NOT touch scam_score, scam_indicators, or is_quarantined.
    """
    from database import get_labels, _get_connection, _release_connection
    from gmail import get_or_create_label, change_label, apply_label

    conn = None
    try:
        # Get current email state from DB
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email_id, label_id, last_applied_label_id
            FROM analyzed_emails
            WHERE email_id = %s AND user_id = %s
        """, (email_id, user_id))

        row = cursor.fetchone()
        if not row:
            _release_connection(conn)
            return {"success": False, "error": "Email not found"}

        current_label_id = row['label_id']
        last_applied_label_id = row['last_applied_label_id']

        # If already synced, ensure the legacy applied flag is also correct.
        if last_applied_label_id == current_label_id and current_label_id is not None:
            cursor.execute("""
                UPDATE analyzed_emails
                SET applied_to_gmail = 1
                WHERE email_id = %s AND user_id = %s
            """, (email_id, user_id))
            conn.commit()
            _release_connection(conn)
            return {"success": True}  # Already synced, nothing else to do

        # Get label names
        labels = get_labels(user_id)
        current_label = next((l for l in labels if l["label_id"] == current_label_id), None)

        if not current_label:
            _release_connection(conn)
            return {"success": False, "error": "Current label not found"}

        current_label_name = current_label["label_name"]

        # Get Gmail label ID for new label (reuse shared cache)
        new_gmail_label_id = get_or_create_label(user_email, current_label_name, user_id, gmail_labels_cache)
        if not new_gmail_label_id:
            _release_connection(conn)
            return {"success": False, "error": "Failed to get/create Gmail label"}

        # Determine if we need to remove old label
        if last_applied_label_id is None:
            # First-ever apply: just add new label
            apply_label(user_email, email_id, new_gmail_label_id)

        elif last_applied_label_id != current_label_id:
            # Label changed: remove old + add new
            old_label = next((l for l in labels if l["label_id"] == last_applied_label_id), None)

            if old_label:
                old_gmail_label_id = get_or_create_label(user_email, old_label["label_name"], user_id, gmail_labels_cache)
            else:
                old_gmail_label_id = None

            # Use existing change_label() from Phase 34
            change_label(user_email, email_id, old_gmail_label_id, new_gmail_label_id)

        # Update DB: mark as applied and record which label was applied
        cursor.execute("""
            UPDATE analyzed_emails
            SET applied_to_gmail = 1,
                last_applied_label_id = %s
            WHERE email_id = %s
        """, (current_label_id, email_id))
        conn.commit()
        _release_connection(conn)

        return {"success": True}

    except Exception as e:
        # Critical: Release connection on exception to prevent pool exhaustion
        if conn:
            _release_connection(conn)
        return {"success": False, "error": f"gmail_api_error: {e}"}


@app.put("/emails/{email_id}/label")
@limiter.limit("30/minute")
async def update_email_label(
    request: Request,
    email_id: str,
    body: UpdateEmailLabelRequest,
    user: dict = Depends(require_auth)
):
    """
    PUT /emails/{email_id}/label — Update email label (manual override).
    Does NOT touch scam_score, scam_indicators, or is_quarantined.
    Atomically updates both database and Gmail, with rollback on Gmail failure.
    FastAPI auto-validates request body via UpdateEmailLabelRequest schema.
    """
    user_id = user["user_id"]
    new_label_name = body.label_name

    # Get user email for thread-safe service creation
    user_email = _request_user_email(request)

    # Apply label change using shared logic
    result = _apply_label_change(email_id, new_label_name, user_id, user_email)

    if not result["success"]:
        return JSONResponse(status_code=500, content={"error": result["error"]})

    # Return updated email
    from database import get_analyzed_emails
    updated_emails = get_analyzed_emails(user_id)
    updated_email = next((e for e in updated_emails if e["email_id"] == email_id), None)

    return {"success": True, "email": updated_email}


@app.post("/emails/batch-label")
@limiter.limit("10/hour")
async def batch_label_update(
    request: Request,
    body: BatchLabelUpdateRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/batch-label — Batch update email labels (manual override).
    Does NOT touch scam_score, scam_indicators, or is_quarantined.
    Processes changes sequentially, returns partial success results.
    FastAPI auto-validates request body via BatchLabelUpdateRequest schema.
    """
    user_id = user["user_id"]
    changes = body.changes

    # Get user email for thread-safe service creation
    user_email = _request_user_email(request)
    if not user_email:
        return JSONResponse(status_code=500, content={"error": "gmail_not_authenticated"})

    # Process changes sequentially
    applied = 0
    failed = 0
    errors = []

    for change in changes:
        email_id = change.email_id
        new_label_name = change.label_name

        # Apply label change using shared logic
        result = _apply_label_change(email_id, new_label_name, user_id, user_email)

        if result["success"]:
            applied += 1
        else:
            failed += 1
            errors.append({
                "email_id": email_id,
                "error": result["error"]
            })

    return {
        "success": True,
        "applied": applied,
        "failed": failed,
        "errors": errors
    }


@app.get("/emails/pending-count")
async def get_pending_count(request: Request, user: dict = Depends(require_auth)):
    """
    GET /emails/pending-count — Count emails needing Gmail sync.
    Returns count of emails where status='labeled' AND applied_to_gmail=0.
    """
    try:
        logger.info("[PENDING-COUNT] Request received")
        user_id = user["user_id"]

        logger.info(f"[PENDING-COUNT] Fetching count for user_id={user_id}")
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            _execute(cursor, f"""
                SELECT COUNT(*) as count
                FROM analyzed_emails
                WHERE user_id = %s
    {PENDING_GMAIL_SYNC_CONDITION}
            """, (user_id,))

            result = cursor.fetchone()
            count = result['count'] if isinstance(result, dict) else result[0]
            logger.info(f"[PENDING-COUNT] Count={count}")
            return {"pending_count": count}
        finally:
            _release_connection(conn)
    except Exception as e:
        logger.error(f"[PENDING-COUNT ERROR] {type(e).__name__}: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to fetch pending count. Please try again."})


@app.post("/emails/apply-all-pending")
async def apply_all_pending(request: Request, user: dict = Depends(require_auth), limit: int = None):
    """
    POST /emails/apply-all-pending — Apply unapplied labels to Gmail.
    Processes emails where status='labeled' AND applied_to_gmail=0.
    Uses _sync_label_to_gmail() which handles label removal correctly.
    
    Args:
        limit: Optional batch size limit. If provided, only processes up to 
               that many pending emails per call. Allows frontend to call in 
               smaller batches (e.g. 100 at a time) to avoid request timeouts.
    """
    user_id = user["user_id"]

    # Get pending email IDs from DB (with optional limit)
    conn = _get_connection()
    cursor = conn.cursor()
    
    if limit is not None and limit > 0:
        _execute(cursor, f"""
            SELECT email_id
            FROM analyzed_emails
            WHERE user_id = %s
    {PENDING_GMAIL_SYNC_CONDITION}
            LIMIT %s
        """, (user_id, limit))
    else:
        _execute(cursor, f"""
            SELECT email_id
            FROM analyzed_emails
            WHERE user_id = %s
    {PENDING_GMAIL_SYNC_CONDITION}
        """, (user_id,))

    pending_emails = [row['email_id'] for row in cursor.fetchall()]
    _release_connection(conn)

    # Get user email for thread-safe service creation
    user_email = _request_user_email(request)
    if not user_email:
        return JSONResponse(status_code=500, content={"error": "gmail_not_authenticated"})

    # Build gmail_labels_cache once for the entire batch (same pattern as analyze_bulk_ordered)
    import asyncio
    from gmail import get_gmail_service
    service = get_gmail_service(user_email)
    if not service:
        return JSONResponse(status_code=500, content={"error": "gmail_not_authenticated"})
        
    gmail_labels_result = await asyncio.to_thread(
        lambda: service.users().labels().list(userId="me").execute()
    )
    gmail_labels_cache = {
        lbl["name"]: lbl["id"] for lbl in gmail_labels_result.get("labels", [])
    }

    # Move the entire sync loop off the event loop using asyncio.to_thread()
    # This prevents blocking the single-worker process during large batches
    def _apply_batch():
        """Synchronous function to process the batch off the event loop."""
        applied = 0
        failed = 0
        errors = []
        
        for email_id in pending_emails:
            result = _sync_label_to_gmail(email_id, user_id, user_email, gmail_labels_cache)
            
            if result["success"]:
                applied += 1
            else:
                failed += 1
                errors.append({"email_id": email_id, "error": result["error"]})
        
        return applied, failed, errors
    
    # Run the blocking batch processing in a thread pool
    applied, failed, errors = await asyncio.to_thread(_apply_batch)

    return {
        "success": True,
        "applied": applied,
        "failed": failed,
        "errors": errors
    }


# ---------- CUSTOM LABELS ENDPOINTS ----------

@app.get("/labels")
async def get_custom_labels(request: Request, user: dict = Depends(require_auth)):
    """GET /labels — Returns all labels for the current user."""
    user_id = user["user_id"]

    return {"labels": get_labels(user_id)}


@app.get("/settings/labels")
async def get_settings_labels(request: Request, user: dict = Depends(require_auth)):
    """GET /settings/labels — Alias for GET /labels for backward compatibility."""
    user_id = user["user_id"]

    return {"labels": get_labels(user_id)}


@app.post("/labels")
async def create_label(
    request: Request,
    body: CreateLabelRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /labels — Create a new custom label.
    FastAPI auto-validates request body via CreateLabelRequest schema.
    """
    user_id = user["user_id"]
    label_name = body.name or body.label_name
    bg_color = body.color or "#3B82F6"
    text_color = "#FFFFFF"

    label_id = add_label(user_id, label_name, bg_color, text_color)
    return {
        "message": "Label created",
        "label": {
            "label_id": label_id,
            "label_name": label_name,
            "bg_color": bg_color,
            "text_color": text_color,
        },
    }


@app.post("/settings/labels")
async def create_settings_label(
    request: Request,
    body: CreateLabelRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /settings/labels — Alias for POST /labels for backward compatibility.
    FastAPI auto-validates request body via CreateLabelRequest schema.
    """
    user_id = user["user_id"]
    label_name = body.name or body.label_name
    bg_color = body.color or "#3B82F6"
    text_color = "#FFFFFF"

    label_id = add_label(user_id, label_name, bg_color, text_color)
    return {
        "message": "Label created",
        "label": {
            "label_id": label_id,
            "label_name": label_name,
            "bg_color": bg_color,
            "text_color": text_color,
        },
    }


@app.delete("/labels/{label_id}")
async def remove_label(label_id: int, request: Request, user: dict = Depends(require_auth)):
    """DELETE /labels/{label_id} — Delete a custom label."""
    user_id = user["user_id"]

    delete_label(label_id, user_id)
    return {"message": "Label deleted"}


@app.delete("/settings/labels/{label_name}")
async def remove_settings_label(label_name: str, request: Request, user: dict = Depends(require_auth)):
    """DELETE /settings/labels/{label_name} — Backward compat delete by name."""
    user_id = user["user_id"]

    from database import get_label_id_by_name
    try:
        label_id = get_label_id_by_name(user_id, label_name)
        delete_label(label_id, user_id)
        return {"message": "Label deleted"}
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Label not found"})


# ---------- SETTINGS ENDPOINTS ----------

@app.post("/settings/reset-database")
async def reset_database_endpoint(request: Request, user: dict = Depends(require_auth)):
    """POST /settings/reset-database — Wipes analysis data for the current user."""
    user_id = user["user_id"]

    reset_database(user_id)
    return {"message": "Database wiped successfully. You can now re-fetch emails from the beginning."}


# ---------- DELETE MODE ENDPOINTS ----------

@app.get("/settings/delete-mode")
async def get_delete_mode_endpoint(request: Request, user: dict = Depends(require_auth)):
    """GET /settings/delete-mode — Returns current delete mode ('trash' or 'permanent')."""
    user_id = user["user_id"]
    mode = get_delete_mode(user_id)
    return {"delete_mode": mode}


@app.put("/settings/delete-mode")
async def update_delete_mode_endpoint(
    request: Request,
    body: UpdateDeleteModeRequest,
    user: dict = Depends(require_auth)
):
    """
    PUT /settings/delete-mode — Update delete mode to 'trash' or 'permanent'.
    FastAPI auto-validates request body via UpdateDeleteModeRequest schema.
    """
    user_id = user["user_id"]
    mode = body.mode

    set_delete_mode(user_id, mode)
    return {"message": f"Delete mode set to '{mode}'.", "delete_mode": mode}


# ---------- MARK EMAIL SAFE ----------

@app.patch("/emails/{email_id}/mark-safe")
@limiter.limit("30/minute")
async def patch_mark_email_safe(email_id: str, request: Request, user: dict = Depends(require_auth)):
    """PATCH /emails/{email_id}/mark-safe — Mark an email as safe."""
    user_id = user["user_id"]

    mark_email_safe(email_id, user_id)
    return {"success": True, "message": f"Email {email_id} marked as safe."}


# ---------- AI REWRITE ENDPOINT ----------

MAX_REWRITE_BYTES = 262144
MAX_ATTACHMENTS_BYTES = 18 * 1024 * 1024


async def _bounded_json(request: Request, limit: int) -> dict:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "Request body is too large")
        data.extend(chunk)
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(value, dict):
        raise HTTPException(422, "JSON object required")
    return value


@app.post("/ai/rewrite")
@limiter.limit("10/minute")
async def ai_rewrite(
    request: Request,
    body: AIRewriteRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /ai/rewrite — Rewrite email text using AI with support for long-form content.
    FastAPI auto-validates request body via AIRewriteRequest schema.
    """
    text = body.text
    instruction = body.instruction

    prompt = REWRITE_PROMPT.format(instruction=instruction, text=text)
    result = await ai_router.analyze(prompt)

    if "error" in result:
        return JSONResponse(status_code=503, content=result)

    return {
        "rewritten": result["response"],
        "provider_used": result["provider_used"],
        "character_count_original": len(text),
        "character_count_rewritten": len(result["response"]),
    }


@app.get("/ai/status")
async def ai_status():
    """GET /ai/status — Returns normalized AI provider configuration status."""
    return {"providers": get_provider_status()}


# ---------- SECURITY SCAN ENDPOINT ----------

@app.post("/security/scan-email")
async def security_scan_email(request: Request, user: dict = Depends(require_auth)):
    """POST /security/scan-email — Scan email URLs for threats."""

    from security import extract_urls, scan_url
    import httpx
    import asyncio

    data = await request.json()
    email_id = data.get("email_id", "")
    body = data.get("body", "")

    urls = extract_urls(body)
    threats = []
    
    api_semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls:
            result = await scan_url(url, email_id, client, api_semaphore)
            if result["is_safe"] == 0:
                threats.append(result)

    return {
        "email_id": email_id,
        "urls_checked": len(urls),
        "threats_found": len(threats),
        "threats": threats,
    }


# ---------- QUARANTINE ENDPOINTS ----------

@app.get("/quarantine")
async def quarantine_list(request: Request, user: dict = Depends(require_auth)):
    """GET /quarantine — Returns all quarantined emails."""
    user_id = user["user_id"]

    emails = get_analyzed_emails(user_id)
    quarantined = [e for e in emails if e.get("is_quarantined") == 1]
    return {"emails": quarantined, "count": len(quarantined)}


@app.post("/quarantine/{email_id}/safe")
@limiter.limit("30/minute")
async def quarantine_mark_safe(email_id: str, request: Request, user: dict = Depends(require_auth)):
    """POST /quarantine/{email_id}/safe — Removes quarantine flag."""
    user_id = user["user_id"]
    mark_email_safe(email_id, user_id)
    return {"success": True, "message": f"Email {email_id} marked as safe."}


@app.delete("/quarantine/{email_id}")
@limiter.limit("30/minute")
async def quarantine_delete(email_id: str, request: Request, user: dict = Depends(require_auth)):
    """DELETE /quarantine/{email_id} — Delete email using user's preferred mode."""
    user_id = user["user_id"]

    mode = get_delete_mode(user_id)
    success = delete_email(email_id, user_id, user_email=_request_user_email(request))
    if success:
        mark_email_safe(email_id, user_id)
        action = "permanently deleted" if mode == "permanent" else "moved to trash"
        return {"success": True, "message": f"Email {email_id} {action}."}
    return JSONResponse(status_code=500, content={"error": "Failed to delete email."})


# ---------- SCAM ALERTS ENDPOINT ----------

@app.get("/scam/alerts")
async def scam_alerts(request: Request, min_score: int = 30, user: dict = Depends(require_auth)):
    """GET /scam/alerts?min_score=30 — Returns flagged emails sorted by scam score."""
    user_id = user["user_id"]
    emails = get_analyzed_emails(user_id)
    flagged = [e for e in emails if (e.get("scam_score") or 0) >= min_score]
    flagged.sort(key=lambda x: (x.get("scam_score") or 0), reverse=True)
    return {"emails": flagged, "count": len(flagged)}


@app.post("/scam/reanalyze/{email_id}")
async def reanalyze_scam_email(
    email_id: str,
    request: Request,
    body: ReanalyzeRequest = ReanalyzeRequest(),
    user: dict = Depends(require_auth)
):
    """
    POST /scam/reanalyze/{email_id} — Re-run AI scam analysis on a single email.
    Reuses the same classification pipeline (URL scan + AI cascade) and persists the
    new scam_score, indicators, label, and quarantine flag.
    Returns { scam_score, reason, indicators, label, is_quarantined } for the UI.
    FastAPI auto-validates request body via ReanalyzeRequest schema (optional).
    """
    import httpx
    import asyncio

    user_id = user["user_id"]
    # body.force is available for future force-reanalysis logic

    # Fetch the email's current data
    emails = get_analyzed_emails(user_id)
    email = next((e for e in emails if e["email_id"] == email_id), None)
    if not email:
        return JSONResponse(status_code=404, content={"error": "Email not found"})

    body = email.get("body", "") or ""
    sender = email.get("sender", "") or ""
    subject = email.get("subject", "") or ""
    snippet = email.get("snippet", "") or ""
    
    # Fallback: fetch body from Gmail if DB has empty body (metadata-only fetch)
    if not body:
        from gmail import get_gmail_service, _get_email_body
        user_email = _request_user_email(request)
        service = get_gmail_service(user_email)
        if service:
            body = await asyncio.to_thread(_get_email_body, service, email_id)

    # Available labels for classification
    available_labels_list = get_labels(user_id)
    available_label_names = [lbl["label_name"] for lbl in available_labels_list]
    if not available_label_names:
        return JSONResponse(
            status_code=400,
            content={"error": "no_labels", "message": "You must create at least one label before analysis."},
        )
    default_label = available_label_names[0]

    # Step B — URL extraction and Google Safe Browsing scan
    from security import extract_urls, scan_url
    urls = extract_urls(body)
    
    # Three-state signal: confirmed_threat (verdict_unsafe), scan_unavailable (scan_failed), or no threat
    url_threat_confirmed = False
    url_scan_unavailable = False
    
    if urls:
        async with httpx.AsyncClient(timeout=10.0) as url_client:
            url_semaphore = asyncio.Semaphore(10)
            scan_tasks = [scan_url(url, email_id, url_client, url_semaphore) for url in urls]
            results = await asyncio.gather(*scan_tasks)
            
            # Separate real threats (is_safe=0, threat_type set) from scan failures (is_safe=None or scan_failed=True)
            for r in results:
                if r.get("is_safe") == 0 and r.get("threat_type") is not None:
                    url_threat_confirmed = True  # API confirmed real threat
                elif r.get("scan_failed") or r.get("is_safe") is None:
                    url_scan_unavailable = True  # API call failed, no verdict obtained

    # Step C — AI cascade classification and scam scoring
    prompt = CLASSIFICATION_PROMPT.format(
        sender=sender,
        subject=subject,
        body=body[:1500],
        url_threat_confirmed=url_threat_confirmed,
        url_scan_unavailable=url_scan_unavailable,
        available_labels=", ".join(available_label_names),
    )
    ai_result = await ai_router.analyze_json(prompt)
    provider_used = ai_result.get("provider_used")

    # Defaults — use first available label as fallback
    label = default_label
    scam_score = 0
    scam_indicators = []
    reasoning = ""

    if ai_result.get("data"):
        data = ai_result["data"]
        label = data.get("label", default_label)
        scam_score = data.get("scam_score", 0)
        scam_indicators = data.get("scam_indicators", [])
        reasoning = data.get("reasoning", "")
    elif ai_result.get("error"):
        return JSONResponse(status_code=503, content={"error": ai_result["error"]})

    # Validate label
    if label not in available_label_names:
        label = default_label

    # Validate scam_score (0-100)
    if not isinstance(scam_score, int):
        try:
            scam_score = int(scam_score)
        except (ValueError, TypeError):
            scam_score = 0
    scam_score = max(0, min(100, scam_score))

    # Validate indicators
    if scam_indicators is None or not isinstance(scam_indicators, list):
        scam_indicators = []

    # Apply consolidated quarantine policy
    from quarantine_policy import should_quarantine
    is_quarantined = int(should_quarantine(scam_score, url_threat_confirmed, label))

    # Resolve label_id and persist
    label_id = get_label_id_by_name(user_id, label)
    update_analyzed_email(
        email_id=email_id,
        label_id=label_id,
        scam_score=scam_score,
        scam_indicators=json.dumps(scam_indicators),
        is_quarantined=is_quarantined,
        status='labeled',
        user_id=user_id,
    )

    logger.info(f"[SCAM REANALYZE] {email_id[:12]}... -> label={label}, scam={scam_score}, quarantine={is_quarantined}")
    return {
        "email_id": email_id,
        "scam_score": scam_score,
        "reason": reasoning,
        "indicators": scam_indicators,
        "label": label,
        "is_quarantined": is_quarantined,
        "provider_used": provider_used,
    }


# ---------- BATCH DELETE ENDPOINT ----------

@app.post("/emails/batch-delete")
@limiter.limit("5/hour")
async def emails_batch_delete(
    request: Request,
    body: BatchDeleteRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/batch-delete — Trash and delete matching emails.
    FastAPI auto-validates request body via BatchDeleteRequest schema.
    """
    user_id = user["user_id"]
    mode = body.mode
    value = body.value

    # Get all emails for this user, then filter
    emails = get_analyzed_emails(user_id)

    if mode == "label":
        matching = [e for e in emails if e.get("label_name") == value]
    elif mode == "sender":
        matching = [e for e in emails if value.lower() in (e.get("sender", "")).lower()]

    deleted = 0
    failed = 0

    for email in matching:
        success = delete_email(email["email_id"], user_id, user_email=_request_user_email(request))
        if success:
            deleted += 1
        else:
            failed += 1

    return {"deleted": deleted, "failed": failed, "total": len(matching)}


# ---------- INLINE REPLY ENDPOINT ----------

from fastapi import File, UploadFile, Form

@app.post("/emails/{email_id}/reply")
async def send_reply_endpoint(
    email_id: str, 
    body: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
    user: dict = Depends(require_auth)
):
    """
    POST /emails/{email_id}/reply — Sends a threaded reply with optional attachments.
    
    Args:
        email_id: Email ID to reply to
        body: Reply message text (form field)
        attachments: List of file uploads (optional, max 10 files, 25MB each)
        user: Authenticated user from JWT/session
    """
    if len(body) > 100000:
        return JSONResponse(status_code=413, content={"error": "Reply body is too large."})
    if not body or not body.strip():
        return JSONResponse(status_code=400, content={"error": "Reply body cannot be empty."})

    user_id = user["user_id"]
    user_email = get_user_email_by_id(user_id)

    # Validate attachments
    if len(attachments) > 10:
        return JSONResponse(status_code=400, content={"error": "Maximum 10 attachments allowed."})

    # Reserve room for MIME/base64 overhead under Gmail's 25MB message limit.
    if sum(f.size or 0 for f in attachments) > MAX_ATTACHMENTS_BYTES:
        return JSONResponse(status_code=413, content={"error": "Combined attachments exceed 18MB."})
    attachment_data = []
    total_size = 0

    for upload_file in attachments:
        content = await upload_file.read(MAX_ATTACHMENTS_BYTES - total_size + 1)
        total_size += len(content)
        if total_size > MAX_ATTACHMENTS_BYTES:
            return JSONResponse(status_code=413, content={"error": "Combined attachments exceed 18MB."})
        
        attachment_data.append({
            "filename": upload_file.filename,
            "content": content,
            "mime_type": upload_file.content_type or "application/octet-stream"
        })

    try:
        sent = send_reply(email_id, body, user_email, attachments=attachment_data if attachment_data else None)
        if not sent:
            return JSONResponse(status_code=502, content={"error": "Failed to send reply. Please try again."})
        
        response_message = "Reply sent successfully."
        if attachment_data:
            response_message += f" ({len(attachment_data)} attachment{'s' if len(attachment_data) > 1 else ''} included)"
        
        return {
            "message": response_message, 
            "sent_message_id": sent.get("id"),
            "attachments_count": len(attachment_data)
        }
    except Exception as e:
        logger.error(f"[REPLY ERROR] {type(e).__name__}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to send reply. Please try again."})


# ---------- STATS ENDPOINT ----------

@app.post("/emails/retry-failed")
@limiter.limit("5/hour")
async def retry_failed_emails(request: Request, user: dict = Depends(require_auth)):
    """
    POST /emails/retry-failed — Retry failed analysis records through the analysis pipeline.
    P0-4 fix: Pass exact email IDs to label_only_pipeline instead of using limit.
    """
    user_id = user["user_id"]

    try:
        from database import get_pending_retry_queue
        retry_rows = get_pending_retry_queue(user_id, max_retries=5)
        if not retry_rows:
            return {"success": True, "retried": 0, "message": "No retryable failed emails found"}

        # Extract email IDs for exact targeting
        email_ids = [row["email_id"] for row in retry_rows]

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            for email_id in email_ids:
                _execute(cursor, """
                    UPDATE analyzed_emails
                    SET status = 'fetched'
                    WHERE email_id = %s AND user_id = %s
                """, (email_id, user_id))
            conn.commit()
        finally:
            _release_connection(conn)

        from gmail import label_only_pipeline
        final_event = {"analyzed": 0, "failed": 0}
        # P0-4 fix: Pass exact email_ids instead of limit
        async for event in label_only_pipeline(
            user_id=user_id,
            user_email=_request_user_email(request),
            email_ids=email_ids,  # Exact retry targets
        ):
            final_event = event

        return {
            "success": True,
            "retried": len(retry_rows),
            "result": final_event,
        }

    except Exception as e:
        logger.error(f"[RETRY ERROR] {type(e).__name__}: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to retry emails. Please try again."})


@app.get("/emails/stats")
async def emails_stats(request: Request, user: dict = Depends(require_auth)):
    """GET /emails/stats — Returns summary statistics."""
    user_id = user["user_id"]


    emails = get_analyzed_emails(user_id)
    total_analyzed = len(emails)
    total_quarantined = sum(1 for e in emails if e.get("is_quarantined") == 1)
    total_flagged = sum(1 for e in emails if (e.get("scam_score") or 0) >= 30)

    return {
        "total_analyzed": total_analyzed,
        "total_quarantined": total_quarantined,
        "total_flagged": total_flagged,
    }


# ---------- HEALTH CHECK ----------

@app.get("/")
async def root():
    """GET / — Simple health check endpoint."""
    return {
        "app": "Gmail Manager API",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """
    GET /health — Comprehensive system health endpoint for monitoring.
    
    Returns:
    - status: "healthy" | "degraded" | "unhealthy"
    - timestamp: ISO 8601 timestamp
    - version: API version
    - commit_sha: Git commit hash (from env or "unknown")
    - build_timestamp: Build time (from env or "unknown")
    - database: Connection status + pending queue count
    - uptime: Process uptime in seconds
    - environment: "production" | "development"
    
    Used by:
    - Railway health checks
    - Monitoring dashboards
    - Uptime monitoring services (UptimeRobot, etc.)
    """
    import time
    from datetime import datetime, timezone
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"),
        "build_timestamp": os.getenv("BUILD_TIMESTAMP", "unknown"),
        "environment": "production" if IS_PRODUCTION else "development",
    }
    
    # Database health check
    conn = None
    cursor = None
    query_failed = False
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        
        # Check database connectivity
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Count actionable analysis work, including retryable failures. The
        # `pending` status is not used by the analysis pipeline.
        _execute(cursor, """
            SELECT COUNT(*) AS count
            FROM analyzed_emails ae
            LEFT JOIN retry_queue rq ON rq.email_id = ae.email_id
            WHERE ae.status = 'fetched'
               OR (
                    ae.status = 'failed'
                    AND rq.email_id IS NOT NULL
                    AND rq.retry_count < %s
               )
        """, (MAX_RETRIES,))
        pending_row = cursor.fetchone()
        
        # Get total email count
        _execute(cursor, "SELECT COUNT(*) AS count FROM analyzed_emails")
        total_row = cursor.fetchone()

        def _count_from_row(row):
            if row is None:
                return 0
            if hasattr(row, "keys"):
                return int(row["count"])
            return int(row[0])

        pending_count = _count_from_row(pending_row)
        total_emails = _count_from_row(total_row)
        
        health_status["database"] = {
            "status": "connected",
            "pending_queue_count": pending_count,
            "total_emails": total_emails,
        }
        
    except Exception as e:
        logger.error(f"[Health Check] Database check failed: {e}")
        query_failed = True
        health_status["status"] = "degraded"
        health_status["database"] = {
            "status": "error",
            "error": str(e),
        }
    finally:
        try:
            if cursor is not None:
                cursor.close()
        except Exception as cleanup_error:
            logger.warning(f"[Health Check] Cursor cleanup failed: {cleanup_error}")
        if query_failed and conn is not None:
            try:
                conn.rollback()
            except Exception as cleanup_error:
                logger.warning(f"[Health Check] Transaction rollback failed: {cleanup_error}")
        try:
            if conn is not None:
                _release_connection(conn)
        except Exception as cleanup_error:
            logger.warning(f"[Health Check] Connection cleanup failed: {cleanup_error}")
    
    # Process uptime (seconds since app start)
    try:
        import psutil
        process = psutil.Process(os.getpid())
        uptime_seconds = int(time.time() - process.create_time())
        health_status["uptime_seconds"] = uptime_seconds
    except ImportError:
        # psutil not available - skip uptime metric
        pass
    except Exception as e:
        logger.warning(f"[Health Check] Uptime calculation failed: {e}")
    
    # Scheduler status
    try:
        scheduler_status = get_scheduler_status()
        health_status["scheduler"] = scheduler_status
    except Exception as e:
        logger.warning(f"[Health Check] Scheduler status failed: {e}")
        health_status["scheduler"] = {"running": False, "error": str(e)}
    
    # Return appropriate HTTP status code
    if health_status["status"] == "healthy":
        return JSONResponse(status_code=200, content=health_status)
    elif health_status["status"] == "degraded":
        return JSONResponse(status_code=503, content=health_status)  # Return 503 for degraded state
    else:
        return JSONResponse(status_code=503, content=health_status)


@app.get("/api/ml/active-model-metadata")
async def get_active_model_metadata():
    """
    GET /api/ml/active-model-metadata — Live model metadata from ml_models table.
    
    Returns metadata for the currently active ML model, including:
    - model_version: Timestamp-based version identifier
    - training_date: When the model was trained
    - dataset_info: Total training samples
    - performance: Precision, recall, calibration error
    - model_hash: SHA-256 hash for integrity verification
    
    This endpoint replaces the static model_metadata.json fixture.
    Metadata is live-generated from the database, not manually maintained.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Get active model metadata
        _execute(cursor, """
            SELECT 
                version, 
                trained_at, 
                training_row_count,
                validation_precision,
                validation_recall,
                calibration_error,
                model_hash,
                model_id
            FROM ml_models
            WHERE is_active = 1
            ORDER BY trained_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        
        if not row:
            return JSONResponse(
                status_code=404, 
                content={
                    "error": "No active model found",
                    "message": "Train and activate a model using train_ml_model.py and activate_model.py"
                }
            )
        
        # Build metadata response
        metadata = {
            "model_type": "Logistic Regression with Isotonic Calibration",
            "model_version": row['version'] if isinstance(row, dict) else row[0],
            "training_date": (row['trained_at'] if isinstance(row, dict) else row[1]).isoformat(),
            "dataset_info": {
                "total_emails": row['training_row_count'] if isinstance(row, dict) else row[2],
                "source": "analyzed_emails table (AI-labeled only, excludes rewritten emails)"
            },
            "performance": {
                "precision_high_risk": float(row['validation_precision'] if isinstance(row, dict) else row[3]) if (row['validation_precision'] if isinstance(row, dict) else row[3]) is not None else None,
                "recall_high_risk": float(row['validation_recall'] if isinstance(row, dict) else row[4]) if (row['validation_recall'] if isinstance(row, dict) else row[4]) is not None else None,
                "calibration_error": float(row['calibration_error'] if isinstance(row, dict) else row[5]) if (row['calibration_error'] if isinstance(row, dict) else row[5]) is not None else None
            },
            "security": {
                "model_hash": row['model_hash'] if isinstance(row, dict) else row[6],
                "hash_algorithm": "SHA-256",
                "integrity_verified": True
            },
            "model_id": row['model_id'] if isinstance(row, dict) else row[7]
        }
        
        return metadata
        
    finally:
        _release_connection(conn)


# ---------- BULK EMAIL OPERATIONS (Phase 2: Feature Gaps Sprint) ----------

@app.post("/emails/bulk-delete")
@limiter.limit("10/hour")
async def bulk_delete_emails(
    request: Request,
    body: BulkDeleteRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/bulk-delete — Delete multiple emails at once.
    Max 100 emails per batch. Respects user's delete mode (trash/permanent).
    FastAPI auto-validates request body via BulkDeleteRequest schema.
    """
    user_id = user["user_id"]
    user_email = _request_user_email(request)
    email_ids = body.email_ids
    
    # Delete each email using existing delete_email function
    mode = get_delete_mode(user_id)
    success_count = 0
    failed_ids = []
    
    for email_id in email_ids:
        try:
            if delete_email(email_id, user_id, user_email):
                success_count += 1
            else:
                failed_ids.append(email_id)
        except Exception as e:
            logger.error(f"Failed to delete email {email_id}: {e}")
            failed_ids.append(email_id)
    
    action = "permanently deleted" if mode == "permanent" else "moved to trash"
    
    # Phase 6: Audit log bulk delete operation
    from audit import log_event, ACTION_BULK_DELETE, SEVERITY_WARNING
    log_event(
        user_id=user_id,
        action=ACTION_BULK_DELETE,
        resource_type="email",
        severity=SEVERITY_WARNING,
        metadata={
            "total_requested": len(email_ids),
            "success_count": success_count,
            "failed_count": len(failed_ids),
            "delete_mode": mode,
            "sample_ids": email_ids[:5]  # First 5 for audit trail
        },
        request=request
    )
    
    return {
        "success": True,
        "message": f"Bulk delete complete: {success_count} emails {action}",
        "deleted_count": success_count,
        "failed_count": len(failed_ids),
        "failed_ids": failed_ids[:10]  # Return first 10 failures
    }


@app.post("/emails/bulk-mark-safe")
@limiter.limit("10/hour")
async def bulk_mark_safe(
    request: Request,
    body: BulkMarkSafeRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/bulk-mark-safe — Mark multiple emails as safe at once.
    Max 100 emails per batch. Sets is_quarantined=0, scam_score=0, user_decision=user_safe.
    FastAPI auto-validates request body via BulkMarkSafeRequest schema.
    """
    user_id = user["user_id"]
    email_ids = body.email_ids
    
    from database import bulk_mark_emails_safe
    count = bulk_mark_emails_safe(email_ids, user_id)
    
    # Phase 6: Audit log bulk mark-safe operation
    from audit import log_event, ACTION_BULK_MARK_SAFE, SEVERITY_INFO
    log_event(
        user_id=user_id,
        action=ACTION_BULK_MARK_SAFE,
        resource_type="email",
        severity=SEVERITY_INFO,
        metadata={
            "total_requested": len(email_ids),
            "updated_count": count,
            "sample_ids": email_ids[:5]
        },
        request=request
    )
    
    return {
        "success": True,
        "message": f"Marked {count} emails as safe",
        "updated_count": count
    }


@app.post("/emails/bulk-quarantine")
@limiter.limit("10/hour")
async def bulk_quarantine(
    request: Request,
    body: BulkQuarantineRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/bulk-quarantine — Quarantine multiple emails at once.
    Max 100 emails per batch. Sets user_decision=user_quarantined, is_quarantined=1.
    FastAPI auto-validates request body via BulkQuarantineRequest schema.
    """
    user_id = user["user_id"]
    email_ids = body.email_ids
    
    from database import bulk_quarantine_emails
    count = bulk_quarantine_emails(email_ids, user_id)
    
    # Phase 6: Audit log bulk quarantine operation
    from audit import log_event, ACTION_BULK_QUARANTINE, SEVERITY_WARNING
    log_event(
        user_id=user_id,
        action=ACTION_BULK_QUARANTINE,
        resource_type="email",
        severity=SEVERITY_WARNING,
        metadata={
            "total_requested": len(email_ids),
            "updated_count": count,
            "sample_ids": email_ids[:5]
        },
        request=request
    )
    
    return {
        "success": True,
        "message": f"Quarantined {count} emails",
        "updated_count": count
    }


@app.post("/emails/bulk-label")
@limiter.limit("10/hour")
async def bulk_label(
    request: Request,
    body: BulkLabelRequest,
    user: dict = Depends(require_auth)
):
    """
    POST /emails/bulk-label — Apply label to multiple emails at once.
    Max 100 emails per batch. Updates database and optionally syncs to Gmail.
    FastAPI auto-validates request body via BulkLabelRequest schema.
    
    NOTE: Frontend currently sends 'label_name' (string) but this endpoint
    expects 'label_id' (integer). Frontend must be updated after deployment.
    """
    user_id = user["user_id"]
    user_email = _request_user_email(request)
    email_ids = body.email_ids
    label_id = body.label_id
    
    # Update database
    from database import bulk_update_email_labels
    count = bulk_update_email_labels(email_ids, label_id, user_id)

    # Phase 6: Audit log bulk label operation
    from audit import log_event, ACTION_BULK_LABEL, SEVERITY_INFO
    log_event(
        user_id=user_id,
        action=ACTION_BULK_LABEL,
        resource_type="email",
        severity=SEVERITY_INFO,
        metadata={
            "total_requested": len(email_ids),
            "updated_count": count,
            "label_id": label_id,
            "sample_ids": email_ids[:5]
        },
        request=request
    )
    
    # TODO: Sync to Gmail if sync_enabled (Phase 3 enhancement)
    # For now, database-only update
    
    return {
        "success": True,
        "message": f"Applied label_id {label_id} to {count} emails",
        "updated_count": count
    }


# ---------- AUDIT LOG ENDPOINTS (Phase 6) ----------

@app.get("/api/admin/dead-letter-queue")
async def get_dead_letter_queue_endpoint(
    user: dict = Depends(require_auth),
):
    """Return dead-lettered retry failures for the authenticated user."""
    try:
        from database import get_dead_letter_queue
        return {
            "success": True,
            "failures": get_dead_letter_queue(user["user_id"]),
        }
    except Exception as e:
        logger.error(f"[DLQ] Failed to fetch dead-letter queue: {type(e).__name__}: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve dead-letter queue"})


@app.get("/audit/logs")
async def get_audit_logs(
    request: Request,
    user: dict = Depends(require_auth),
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    GET /audit/logs — Retrieve user's own audit logs.
    
    Query Parameters:
    - limit: Max logs to return (default 50, max 200)
    - offset: Pagination offset (default 0)
    - action: Filter by action type (e.g., 'auth.login', 'bulk.delete')
    - severity: Filter by severity ('info', 'warning', 'critical')
    - start_date: Filter logs after this date (ISO format)
    - end_date: Filter logs before this date (ISO format)
    
    Returns:
    - logs: Array of audit log entries
    - total_count: Total matching logs (for pagination)
    - has_more: Boolean indicating if more pages exist
    
    Security: Users can ONLY view their own audit logs.
    GDPR Compliance: Article 15 (right to access processing logs)
    """
    try:
        user_id = user["user_id"]
        
        from audit import get_user_audit_logs, get_audit_log_count
        
        # Fetch logs with filters
        logs = get_user_audit_logs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            action_filter=action,
            severity_filter=severity,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get total count for pagination
        total_count = get_audit_log_count(
            user_id=user_id,
            action_filter=action,
            severity_filter=severity,
            start_date=start_date,
            end_date=end_date,
        )
        
        has_more = (offset + len(logs)) < total_count
        
        return {
            "success": True,
            "logs": logs,
            "total_count": total_count,
            "returned_count": len(logs),
            "offset": offset,
            "has_more": has_more,
        }
    
    except Exception as e:
        logger.error(f"[AUDIT] Failed to fetch logs: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve audit logs"})


@app.post("/audit/cleanup")
async def cleanup_audit_logs(
    request: Request,
    user: dict = Depends(require_auth),
    retention_days: int = 90,
):
    """
    POST /audit/cleanup — Cleanup audit logs older than retention period.
    
    Body:
    - retention_days: Days to retain logs (default 90, GDPR compliance)
    
    Security: Admin-only endpoint (not implemented in v1, returns 403)
    Future: Add admin role check before allowing cleanup
    """
    return JSONResponse(
        status_code=403,
        content={"error": "Admin-only endpoint. Automated cleanup runs daily via cron."}
    )


# ---------- RUN SERVER ----------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

