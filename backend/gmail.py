"""
gmail.py — Gmail API Integration Module (Restructured)
Fetches emails from the user's Gmail inbox using the Gmail API.
Uses the OAuth token from auth.py for authentication.
Includes the hybrid ML + AI cascade pipeline (Steps A through I).
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import json
import asyncio
import socket
socket.setdefaulttimeout(15)
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
import httpx
import socket
socket.setdefaulttimeout(15)
from auth import get_credentials
from database import (
    is_already_analyzed, save_analyzed_email,
    get_scan_cursor, save_scan_cursor,
    get_labels, get_label_id_by_name,
    get_user_email_by_id,
    add_to_retry_queue, remove_from_retry_queue,
)
from ml_inference import predict_async, is_model_available, log_disagreement


def get_gmail_service(user_email: str = None):
    """
    Build and return a Gmail API service instance for a specific user.
    Uses the DB-stored OAuth credentials for that user (keyed by gmail_address).
    Returns None if the user is not authenticated.
    """
    creds = get_credentials(user_email)
    if not creds:
        logger.info("[GMAIL] No valid credentials found. User needs to log in.")
        return None

    service = build("gmail", "v1", credentials=creds)
    logger.info("[GMAIL] Gmail service initialized.")
    return service


def fetch_emails(limit: int = 50, page_token: str | None = None, user_email: str = None) -> dict:
    """
    Fetch emails from Gmail in reverse chronological order (newest first).
    Uses parallel fetching for dramatically faster email retrieval.

    Args:
        limit: Maximum number of emails to retrieve (default 50)
        page_token: Gmail pagination token for fetching the next page

    Returns:
        Dict with keys:
          - emails: list[dict] — the parsed emails
          - next_page_token: str | None — cursor for the next scan
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    service = get_gmail_service(user_email)
    if not service:
        return {"emails": [], "next_page_token": None}

    try:
        # Step 1: Collect message IDs (lightweight API call — only returns id + threadId)
        message_ids = []
        current_token = page_token

        import sys

        logger.info(f"[GMAIL] Starting list loop... limit={limit}, token={page_token}")

        while len(message_ids) < limit:
            logger.info(f"[GMAIL] Requesting list batch...")
            response = service.users().messages().list(
                userId="me",
                maxResults=min(limit - len(message_ids), 50),
                pageToken=current_token if current_token else None,
            ).execute()

            messages = response.get("messages", [])
            logger.info(f"[GMAIL] Received batch of {len(messages)} messages.")
            if not messages:
                break

            message_ids.extend([msg["id"] for msg in messages])

            current_token = response.get("nextPageToken")
            logger.info(f"[GMAIL] current message batch size is {len(message_ids)}. Next token is {current_token}")
            if not current_token:
                break

        message_ids = message_ids[:limit]
        logger.info(f"[GMAIL] Got {len(message_ids)} message IDs. Fetching details via batch HTTP...")

        # Step 2: Fetch full details using Gmail's batch endpoint.
        # Gmail enforces a hard cap of 50 sub-requests per batch, so we chunk
        # into groups of 50 and run those chunks concurrently across threads
        # (each thread builds its own Gmail service instance to avoid
        # httplib2 shared-connection deadlock).
        creds = get_credentials(user_email)
        chunks = [message_ids[i:i + 50] for i in range(0, len(message_ids), 50)]
        collected = []
        with ThreadPoolExecutor(max_workers=min(4, len(chunks) or 1)) as executor:
            future_to_chunk = {
                executor.submit(_get_email_details_batch_threadsafe, creds, chunk): chunk
                for chunk in chunks
            }
            for future in as_completed(future_to_chunk):
                collected.extend(future.result())

        # Preserve original order (reverse-chronological from Gmail)
        id_order = {mid: idx for idx, mid in enumerate(message_ids)}
        collected.sort(key=lambda e: id_order.get(e["id"], 999))

        logger.info(f"[GMAIL] Fetched {len(collected)} emails (batched). Next cursor: {current_token}")

        return {
            "emails": collected,
            "next_page_token": current_token,
        }

    except Exception as e:
        logger.info(f"[GMAIL] Error fetching emails: {e}")
        return {"emails": [], "next_page_token": None}


def _parse_email_metadata(email_id: str, msg: dict) -> dict:
    """
    Parse a Gmail messages().get(format="metadata") response into our
    internal email dict shape. Shared by both the single-fetch and
    batch-fetch code paths so parsing logic stays in one place.
    Body is left empty - fetched on-demand via _get_email_body().
    """
    from datetime import datetime, timezone
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    try:
        received_at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc).isoformat()
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        received_at = None

    return {
        "id": email_id,
        "subject": headers.get("subject", "(No Subject)"),
        "sender": headers.get("from", "(Unknown Sender)"),
        "snippet": msg.get("snippet", ""),
        "date": headers.get("date", ""),
        "received_at": received_at,
        "labels": msg.get("labelIds", []),
        "body": "",  # Empty - body fetched on-demand via _get_email_body()
    }


def _get_email_details_batch_threadsafe(creds, email_ids: list[str]) -> list[dict]:
    """
    Thread-safe wrapper: builds its own Gmail service instance per call
    (to avoid httplib2 shared-connection deadlocks) and fetches up to 50
    messages' metadata in a single Gmail BatchHttpRequest (1 HTTP round-trip
    instead of one per message).
    """
    try:
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return _get_email_details_batch(svc, email_ids)
    except Exception as e:
        logger.info(f"[GMAIL] Batch fetch failed for chunk of {len(email_ids)}: {e}")
        return []


def _get_email_details_batch(service, email_ids: list[str]) -> list[dict]:
    """
    Fetch lightweight metadata for up to 50 emails in a single Gmail
    BatchHttpRequest. Gmail caps batches at 50 sub-requests; callers are
    responsible for chunking larger ID lists before calling this.
    """
    if not email_ids:
        return []

    import time

    results: dict[str, dict] = {}
    pending_ids = list(email_ids)

    for attempt in range(3):
        if not pending_ids:
            break

        errors: dict[str, Exception] = {}

        def _callback(request_id, response, exception):
            if exception is not None:
                errors[request_id] = exception
            else:
                results[request_id] = response

        batch = service.new_batch_http_request(callback=_callback)
        for mid in pending_ids:
            batch.add(
                service.users().messages().get(
                    userId="me",
                    id=mid,
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                ),
                request_id=mid,
            )

        batch.execute()
        pending_ids = []
        retry_ids = []
        for mid, exc in errors.items():
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 429:
                retry_ids.append(mid)
            else:
                logger.info(f"[GMAIL] Error fetching email {mid} (batch): {exc}")

        if retry_ids:
            pending_ids = retry_ids
            if attempt < 2:
                delay = 2 ** attempt
                logger.info(f"[GMAIL] Batch fetch rate-limited for {len(retry_ids)} emails; retrying in {delay}s")
                time.sleep(delay)

    for mid in pending_ids:
        logger.info(f"[GMAIL] Dropping email {mid} after batch fetch retries")

    return [_parse_email_metadata(mid, results[mid]) for mid in email_ids if mid in results]


def _get_email_details_threadsafe(creds, email_id: str) -> dict | None:
    """
    Thread-safe wrapper: builds its own Gmail service instance per call
    to avoid httplib2 shared-connection deadlocks.
    """
    try:
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return _get_email_details(svc, email_id)
    except Exception as e:
        logger.info(f"[GMAIL] Thread-safe fetch failed for {email_id}: {e}")
        return None


def _get_email_details(service, email_id: str) -> dict | None:
    """
    Fetch lightweight metadata for a single email by its ID.
    Extracts subject, sender, snippet, date, and labels (no body - use _get_email_body for that).
    Body is deferred to on-demand fetch via _get_email_body() to reduce initial fetch payload size.
    """
    try:
        msg = service.users().messages().get(
            userId="me",
            id=email_id,
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()

        return _parse_email_metadata(email_id, msg)

    except Exception as e:
        logger.info(f"[GMAIL] Error fetching email {email_id}: {e}")
        return None


def _get_email_body(service, email_id: str) -> str:
    """
    Fetch only the body text of a single email by its ID.
    Use this after _get_email_details() when body content is needed for AI analysis.
    IMPROVED (2026-09-11): Enhanced with inline image embedding support.
    """
    try:
        msg = service.users().messages().get(
            userId="me",
            id=email_id,
            format="full",
        ).execute()

        return _extract_body_with_images(msg.get("payload", {}))

    except Exception as e:
        logger.info(f"[GMAIL] Error fetching body for email {email_id}: {e}")
        return ""


def _extract_body_with_images(payload: dict) -> str:
    """
    Extract email body with inline images embedded as data URIs.
    IMPROVED (2026-09-11): Converts cid: references to base64 data URIs.
    
    Gmail structure:
    - multipart/related: HTML body + inline images (with Content-ID)
    - Images referenced as <img src="cid:image_id"> in HTML
    - We convert these to data URIs for display
    """
    import base64
    import re

    def decode_part(data_str: str) -> str:
        """Decode base64url-encoded Gmail payload data."""
        if not data_str:
            return ""
        try:
            return base64.urlsafe_b64decode(data_str).decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug(f"[GMAIL] Failed to decode part: {e}")
            return ""

    def decode_image_data(data_str: str) -> bytes:
        """Decode base64url-encoded image data as bytes."""
        if not data_str:
            return b""
        try:
            return base64.urlsafe_b64decode(data_str)
        except Exception as e:
            logger.debug(f"[GMAIL] Failed to decode image: {e}")
            return b""

    # Collect inline images with their Content-IDs
    inline_images = {}  # {content_id: {"mime": "image/png", "data": bytes}}

    def collect_inline_images(payload: dict):
        """Recursively collect all inline images from the payload."""
        parts = payload.get("parts", [])
        for part in parts:
            mime_type = part.get("mimeType", "")
            
            # Inline image attachment
            if mime_type.startswith("image/"):
                headers = {h["name"].lower(): h["value"] for h in part.get("headers", [])}
                content_id = headers.get("content-id", "").strip("<>")
                
                if content_id:
                    image_data = part.get("body", {}).get("data", "")
                    if image_data:
                        inline_images[content_id] = {
                            "mime": mime_type,
                            "data": decode_image_data(image_data)
                        }
            
            # Recurse into nested parts
            if part.get("parts"):
                collect_inline_images(part)

    def find_html_part(payload: dict, depth: int = 0) -> str:
        """Recursively search for text/html parts."""
        if depth > 10:
            return ""
        
        mime_type = payload.get("mimeType", "")
        
        # Direct HTML part
        if mime_type == "text/html":
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                return decode_part(body_data)
        
        # Multipart container
        if mime_type.startswith("multipart/"):
            parts = payload.get("parts", [])
            
            # For multipart/alternative, prefer HTML
            if mime_type == "multipart/alternative":
                html_content = ""
                plain_content = ""
                
                for part in parts:
                    part_mime = part.get("mimeType", "")
                    if part_mime == "text/html":
                        body_data = part.get("body", {}).get("data", "")
                        if body_data:
                            html_content = decode_part(body_data)
                    elif part_mime == "text/plain":
                        body_data = part.get("body", {}).get("data", "")
                        if body_data:
                            plain_content = decode_part(body_data)
                    elif part_mime.startswith("multipart/"):
                        result = find_html_part(part, depth + 1)
                        if result:
                            return result
                
                return html_content or plain_content
            
            # For other multipart types, search recursively
            for part in parts:
                result = find_html_part(part, depth + 1)
                if result:
                    return result
        
        return ""

    def find_plain_part(payload: dict, depth: int = 0) -> str:
        """Fallback: search for text/plain parts."""
        if depth > 10:
            return ""
        
        mime_type = payload.get("mimeType", "")
        
        if mime_type == "text/plain":
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                return decode_part(body_data)
        
        if mime_type.startswith("multipart/"):
            for part in payload.get("parts", []):
                result = find_plain_part(part, depth + 1)
                if result:
                    return result
        
        return ""

    # Step 1: Collect all inline images
    collect_inline_images(payload)

    # Step 2: Extract HTML body
    html_body = ""
    
    # Try direct body data first (simple emails)
    if "body" in payload and payload["body"].get("data"):
        html_body = decode_part(payload["body"]["data"])
    else:
        # Try HTML extraction
        html_body = find_html_part(payload)
        
        # Fallback to plain text
        if not html_body:
            html_body = find_plain_part(payload)

    # Step 3: Replace cid: references with data URIs
    if html_body and inline_images:
        def replace_cid(match):
            cid = match.group(1)
            if cid in inline_images:
                img_data = inline_images[cid]
                # Convert bytes to base64
                b64_data = base64.b64encode(img_data["data"]).decode("ascii")
                return f'src="data:{img_data["mime"]};base64,{b64_data}"'
            return match.group(0)  # Return original if no match
        
        # Replace all cid: references
        html_body = re.sub(r'src=["\']cid:([^"\']+)["\']', replace_cid, html_body, flags=re.IGNORECASE)

    return html_body


# ---------- GMAIL LABEL MANAGEMENT ----------

# Gmail API only accepts colors from this fixed palette.
# Full list: https://developers.google.com/gmail/api/reference/rest/v1/users.labels
GMAIL_LABEL_COLORS = [
    # (backgroundColor, textColor)
    ("#000000", "#ffffff"), ("#434343", "#ffffff"), ("#666666", "#ffffff"),
    ("#999999", "#ffffff"), ("#cccccc", "#000000"), ("#efefef", "#000000"),
    ("#f3f3f3", "#000000"), ("#ffffff", "#000000"),
    ("#fb4c2f", "#ffffff"), ("#ffad47", "#000000"), ("#fad165", "#000000"),
    ("#16a766", "#ffffff"), ("#43d692", "#000000"), ("#4a86e8", "#ffffff"),
    ("#a479e2", "#ffffff"), ("#f691b3", "#000000"), ("#f6c5be", "#000000"),
    ("#ffe6c7", "#000000"), ("#fef1d1", "#000000"), ("#b9e4d0", "#000000"),
    ("#c6f3de", "#000000"), ("#c9daf8", "#000000"), ("#e4d7f5", "#000000"),
    ("#fcdee8", "#000000"), ("#efa093", "#000000"), ("#ffd6a2", "#000000"),
    ("#fce8b3", "#000000"), ("#89d3b2", "#000000"), ("#a0eac9", "#000000"),
    ("#a4c2f4", "#000000"), ("#b694e8", "#000000"), ("#f7a7c0", "#000000"),
    ("#cc3a21", "#ffffff"), ("#eaa041", "#000000"), ("#f2c960", "#000000"),
    ("#149e60", "#ffffff"), ("#3dc789", "#000000"), ("#3c78d8", "#ffffff"),
    ("#8e63ce", "#ffffff"), ("#e07798", "#000000"), ("#ac2b16", "#ffffff"),
    ("#cf8933", "#000000"), ("#d5ae49", "#000000"), ("#0b804b", "#ffffff"),
    ("#2a9c68", "#000000"), ("#285bac", "#ffffff"), ("#653e9b", "#ffffff"),
    ("#b65775", "#ffffff"), ("#822111", "#ffffff"), ("#a46a21", "#000000"),
    ("#aa8831", "#000000"), ("#076239", "#ffffff"), ("#1a764d", "#000000"),
    ("#1c4587", "#ffffff"), ("#41236d", "#ffffff"), ("#83334c", "#ffffff"),
]


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _color_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance between two RGB tuples."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def _nearest_gmail_color(hex_bg: str, hex_text: str) -> tuple:
    """
    Map an arbitrary hex color pair to the nearest Gmail-approved label color.
    Returns (backgroundColor, textColor) from the Gmail palette.
    """
    target_rgb = _hex_to_rgb(hex_bg)
    best = GMAIL_LABEL_COLORS[0]
    best_dist = float("inf")

    for gmail_bg, gmail_text in GMAIL_LABEL_COLORS:
        dist = _color_distance(target_rgb, _hex_to_rgb(gmail_bg))
        if dist < best_dist:
            best_dist = dist
            best = (gmail_bg, gmail_text)

    return best


def get_or_create_label(user_email: str, label_name: str, user_id: int, gmail_labels_cache: dict[str, str]) -> str | None:
    """
    Get an existing Gmail label by name, or create it if it doesn't exist.
    Maps database colors to Gmail-approved palette colors.
    
    Builds a thread-local Gmail service object to ensure thread safety.

    Args:
        user_email: Gmail address for authentication (builds fresh service per call)
        label_name: The label name (e.g., "Work", "Finance")
        user_id: The user ID for fetching label colors
        gmail_labels_cache: Cache mapping label names to IDs (shared across batch)

    Returns:
        The label ID string, or None on failure
    """
    # Build fresh service per call for thread safety (httplib2.Http is not thread-safe)
    service = get_gmail_service(user_email)
    if not service:
        return None
        
    try:
        labels_db = get_labels(user_id)
        label_info = next(
            (l for l in labels_db if l["label_name"].casefold() == label_name.casefold()),
            None,
        )

        db_bg = label_info["bg_color"] if label_info else "#999999"
        db_text = label_info["text_color"] if label_info else "#FFFFFF"

        # Map to Gmail-approved colors (arbitrary hex causes 400 errors)
        gmail_bg, gmail_text = _nearest_gmail_color(db_bg, db_text)

        # Check the batch-scoped Gmail label cache before making an API call.
        prefix = f"GM/{label_name}"
        cached_label_id = gmail_labels_cache.get(prefix)
        if cached_label_id:
            return cached_label_id

        # Create new label with Gmail-approved colors
        label_body = {
            "name": prefix,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
            "color": {"backgroundColor": gmail_bg, "textColor": gmail_text},
        }

        created = service.users().labels().create(userId="me", body=label_body).execute()
        gmail_labels_cache[prefix] = created["id"]
        logger.info(f"[GMAIL] Created new label '{prefix}' (ID: {created['id']}, color: {gmail_bg}).")
        return created["id"]

    except Exception as e:
        # Surface the full error so label sync issues are visible
        logger.info(f"[GMAIL] ERROR creating/getting label '{label_name}': {type(e).__name__}: {e}")
        return None


def apply_label(user_email: str, email_id: str, label_id: str):
    """
    Apply a Gmail label to a specific email.
    Builds a thread-local Gmail service object to ensure thread safety.
    """
    # Build fresh service per call for thread safety (httplib2.Http is not thread-safe)
    service = get_gmail_service(user_email)
    if not service:
        raise RuntimeError("Gmail service unavailable")
    service.users().messages().modify(
        userId="me", id=email_id, body={"addLabelIds": [label_id]},
    ).execute()
    actual = service.users().messages().get(
        userId="me", id=email_id, format="minimal",
    ).execute()
    if label_id not in actual.get("labelIds", []):
        raise RuntimeError("Gmail label application could not be verified")
    return True


def change_label(user_email: str, email_id: str, old_label_id: str | None, new_label_id: str):
    """
    Replace one Gmail label with another on an email.
    Removes old_label_id (if provided) and adds new_label_id in a single modify() call.
    Builds a thread-local Gmail service object to ensure thread safety.
    """
    # Build fresh service per call for thread safety (httplib2.Http is not thread-safe)
    service = get_gmail_service(user_email)
    if not service:
        logger.info(f"[GMAIL] Cannot change label: service unavailable for {user_email}")
        return
        
    try:
        body = {}
        if old_label_id:
            body["removeLabelIds"] = [old_label_id]
        if new_label_id:
            body["addLabelIds"] = [new_label_id]

        service.users().messages().modify(
            userId="me",
            id=email_id,
            body=body,
        ).execute()
        logger.info(f"[GMAIL] Changed label on {email_id[:12]}... (removed: {old_label_id or 'none'}, added: {new_label_id})")
    except Exception as e:
        logger.info(f"[GMAIL] Error changing label on {email_id}: {e}")
        raise


def trash_email(email_id: str, user_email: str = None) -> bool:
    """Move an email to Gmail trash (NOT permanent delete)."""
    service = get_gmail_service(user_email)
    if not service:
        return False

    try:
        service.users().messages().trash(userId="me", id=email_id).execute()
        logger.info(f"[GMAIL] Trashed email {email_id[:12]}...")
        return True
    except Exception as e:
        logger.info(f"[GMAIL] Error trashing email {email_id}: {e}")
        return False


def permanently_delete_email(email_id: str, user_email: str = None) -> bool:
    """Permanently delete an email from Gmail (IRREVERSIBLE)."""
    service = get_gmail_service(user_email)
    if not service:
        return False

    try:
        service.users().messages().delete(userId="me", id=email_id).execute()
        logger.info(f"[GMAIL] PERMANENTLY DELETED email {email_id[:12]}...")
        return True
    except Exception as e:
        logger.info(f"[GMAIL] Error permanently deleting email {email_id}: {e}")
        return False


def send_reply(email_id: str, reply_body: str, user_email: str = None, attachments: list = None) -> dict | None:
    """
    Send a reply to an existing email with optional attachments.
    Correctly threaded via Message-ID/References so Gmail displays it as a reply.
    
    Args:
        email_id: Original email ID to reply to
        reply_body: Reply message text
        user_email: User's Gmail address
        attachments: List of dicts with 'filename', 'content' (bytes), and 'mime_type'
    
    Returns the sent message's Gmail ID dict on success, None on failure.
    """
    service = get_gmail_service(user_email)
    if not service:
        return None

    try:
        original = service.users().messages().get(
            userId="me",
            id=email_id,
            format="metadata",
            metadataHeaders=["Subject", "From", "Message-ID", "References"],
        ).execute()

        headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
        original_subject = headers.get("Subject", "")
        original_from = headers.get("From", "")
        original_message_id = headers.get("Message-ID", "")
        original_references = headers.get("References", "")

        if not original_from:
            logger.info(f"[GMAIL] Cannot reply to {email_id}: no From header found")
            return None

        reply_subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"
        references = f"{original_references} {original_message_id}".strip() if original_references else original_message_id

        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders

        # Create message with attachments if present
        if attachments and len(attachments) > 0:
            mime_message = MIMEMultipart()
            mime_message.attach(MIMEText(reply_body, 'plain'))
            
            # Add each attachment
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename={attachment["filename"]}'
                )
                if 'mime_type' in attachment:
                    part.set_type(attachment['mime_type'])
                mime_message.attach(part)
        else:
            mime_message = MIMEText(reply_body, 'plain')

        # Set headers
        mime_message["To"] = original_from
        mime_message["Subject"] = reply_subject
        if original_message_id:
            mime_message["In-Reply-To"] = original_message_id
        if references:
            mime_message["References"] = references

        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
        thread_id = original.get("threadId")

        sent = service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id} if thread_id else {"raw": raw},
        ).execute()

        attachment_info = f" with {len(attachments)} attachment(s)" if attachments else ""
        logger.info(f"[GMAIL] Reply sent{attachment_info} for {email_id[:12]}... -> new message {sent.get('id', '')[:12]}...")
        return sent

    except Exception as e:
        logger.info(f"[GMAIL] Error sending reply for {email_id}: {e}")
        return None


def delete_email(email_id: str, user_id: int, user_email: str = None) -> bool:
    """
    Delete an email using the user's preferred mode (trash or permanent).
    Reads delete_mode from the database.
    """
    from database import get_delete_mode

    if user_email is None and user_id is not None:
        user_email = get_user_email_by_id(user_id)

    mode = get_delete_mode(user_id)
    if mode == "permanent":
        return permanently_delete_email(email_id, user_email)
    else:
        return trash_email(email_id, user_email)


# ---------- BULK AI ANALYSIS PIPELINE (Steps A through I) ----------

async def _fetch_new_emails(limit: int, user_id: int, user_email: str):
    """Fetch newest pages until ``limit`` unanalyzed emails are collected."""
    new_emails = []
    skipped_count = 0
    fetched_count = 0
    page_token = None

    while len(new_emails) < limit:
        fetch_result = await asyncio.wait_for(
            asyncio.to_thread(
                fetch_emails,
                limit=limit - len(new_emails),
                page_token=page_token,
                user_email=user_email,
            ),
            timeout=60,
        )
        fetched_emails = fetch_result["emails"]
        fetched_count += len(fetched_emails)

        for email in fetched_emails:
            if is_already_analyzed(email["id"], user_id):
                skipped_count += 1
            else:
                new_emails.append(email)

        next_page_token = fetch_result.get("next_page_token")
        if not fetched_emails or not next_page_token:
            break
        page_token = next_page_token

    return new_emails, skipped_count, fetched_count


async def analyze_bulk_ordered(limit: int = 50, user_id: int = None, user_email: str = None):
    """
    AI-only bulk analysis engine with semaphore-controlled concurrency.
    Yields progress events via SSE as emails finish processing.
    Processes exactly `limit` emails per scan in reverse chronological order.
    Every email passes through the AI cascade — no rule-based shortcuts.

    Args:
        limit: Maximum number of emails to process
        user_id: The authenticated user's ID
        user_email: The authenticated user's gmail_address (used to load their token)
    """
    from ai_router import ai_router, CLASSIFICATION_PROMPT
    from security import extract_urls, scan_url
    import httpx
    import time

    t_bulk_start = time.perf_counter()

    if user_email is None and user_id is not None:
        user_email = get_user_email_by_id(user_id)

    semaphore = asyncio.Semaphore(2)
    url_semaphore = asyncio.Semaphore(8)
    service = get_gmail_service(user_email)
    if not service or user_id is None:
        yield {
            "type": "complete",
            "analyzed": 0,
            "skipped": 0,
            "failed": 0,
            "results": [],
        }
        return

    gmail_labels_result = await asyncio.to_thread(
        lambda: service.users().labels().list(userId="me").execute()
    )
    gmail_labels_cache = {
        lbl["name"]: lbl["id"] for lbl in gmail_labels_result.get("labels", [])
    }

    # Cache labels once per bulk run (instead of per-email DB query)
    available_labels_list = await asyncio.to_thread(get_labels, user_id)
    available_label_names = [lbl["label_name"] for lbl in available_labels_list]
    
    if not available_label_names:
        logger.warning(f"[PIPELINE] Empty label list for user_id={user_id} — analysis will produce unavailable category_status")

    async with httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=50)) as url_client:
        # Emit initializing event immediately so the frontend gets instant feedback
        yield {
            "type": "initializing",
            "message": "Fetching emails from Gmail...",
        }

        # Fetch emails starting from the latest, continuing across pages when
        # deduplication leaves fewer than the requested number of new emails.
        try:
            new_emails, skipped_count, fetched_count = await _fetch_new_emails(
                limit, user_id, user_email
            )
        except asyncio.TimeoutError:
            yield {
                "type": "complete",
                "analyzed": 0,
                "skipped": 0,
                "failed": 0,
                "results": [],
                "error": "Gmail fetch timed out after 60 seconds. Check network connectivity.",
            }
            return

        logger.info(f"[PIPELINE] {len(new_emails)} new emails to analyze, {skipped_count} already cached.")

        total = len(new_emails)
        if total == 0:
            yield {
                "type": "complete",
                "analyzed": 0,
                "skipped": skipped_count,
                "failed": 0,
                "results": [],
            }
            return

        # Create parallel analysis tasks
        tasks = []
        try:
            tasks = [
                asyncio.create_task(_analyze_one(
                    email=email,
                    semaphore=semaphore,
                    ai_router=ai_router,
                    classification_prompt=CLASSIFICATION_PROMPT,
                    user_id=user_id,
                    user_email=user_email,
                    service=service,
                    url_client=url_client,
                    url_semaphore=url_semaphore,
                    available_label_names=available_label_names,
                    gmail_labels_cache=gmail_labels_cache,
                ))
                for email in new_emails
            ]

            # Yield progress as tasks complete
            completed = 0
            failed_count = 0
            all_results = []

            for task in asyncio.as_completed(tasks):
                res = await task
                completed += 1

                if res["status"] == "failed":
                    failed_count += 1

                all_results.append(res)

                # Step I — Send SSE progress event
                yield {
                    "type": "email_done",
                    "email_id": res.get("email_id", ""),
                    "sender": res.get("sender", ""),
                    "subject": res.get("subject", ""),
                    "label": res.get("label", ""),
                    "scam_score": res.get("scam_score", 0),
                    "is_quarantined": res.get("is_quarantined", 0),
                    "progress": completed,
                    "total": total,
                }

            # Final summary
            analyzed_count = sum(1 for r in all_results if r["status"] == "success")

            t_bulk_total = time.perf_counter() - t_bulk_start
            logger.info(f"[TIMING] BULK COMPLETE: total_time={t_bulk_total:.2f}s analyzed={analyzed_count} "
                  f"skipped={skipped_count} failed={failed_count} "
                  f"(fetched {fetched_count} emails, {len(new_emails)} were new)")

            yield {
                "type": "complete",
                "analyzed": analyzed_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "results": all_results,
            }
        finally:
            # Cancel any tasks still in flight (e.g. SSE disconnect injected GeneratorExit)
            # before url_client closes, so they never call client.post() on a closed client.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


def _analysis_text(body: str) -> str:
    """Remove markup before budgeting prompt text, without altering display HTML."""
    from html.parser import HTMLParser

    class TextParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.hidden = 0
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style", "head"}:
                self.hidden += 1

        def handle_endtag(self, tag):
            if tag in {"script", "style", "head"}:
                self.hidden = max(0, self.hidden - 1)

        def handle_data(self, data):
            if not self.hidden:
                self.parts.append(data)

    parser = TextParser()
    parser.feed(body)
    return " ".join(" ".join(parser.parts).split())


def _final_analysis_status(routed_status, url_scan_unavailable, label_id):
    """Return the analysis status that is stored and shown.

    v2_routing reports success as 'complete'. The stored and displayed
    vocabulary is 'completed'. Anything not fully successful is 'partial'.
    """
    if routed_status == "complete":
        routed_status = "completed"
    if routed_status != "completed" or url_scan_unavailable or label_id is None:
        return "partial"
    return "completed"


async def _analyze_one(email: dict, semaphore: asyncio.Semaphore,
                       ai_router, classification_prompt: str,
                       user_id: int, user_email: str, service,
                       url_client: httpx.AsyncClient,
                       url_semaphore: asyncio.Semaphore,
                       available_label_names: list[str],
                       gmail_labels_cache: dict[str, str],
                       update_mode: bool = False) -> dict:
    """Persist a suggestion and its evidence; Gmail changes require explicit approval."""
    from security import extract_urls, scan_url
    from database import update_analyzed_email

    async with semaphore:
        email_id = email["id"]
        subject = email.get("subject", "(No Subject)")
        sender = email.get("sender", "(Unknown)")
        body = email.get("body", "")
        snippet = email.get("snippet", "")
        received_at = email.get("received_at")
        url_threat_confirmed = False
        urls_total = urls_checked = 0
        url_scan_status = "unavailable"
        base = {"email_id": email_id, "subject": subject, "sender": sender}

        def persist(**values):
            if update_mode:
                update_analyzed_email(email_id=email_id, user_id=user_id, **values)
            else:
                save_analyzed_email(email_id=email_id, user_id=user_id, snippet=snippet,
                                    sender=sender, subject=subject, body=body, **values)

        try:
            if not update_mode and is_already_analyzed(email_id, user_id):
                return {**base, "status": "skipped", "label": "", "scam_score": None, "is_quarantined": 0}
            if not body:
                # Build a thread-local service: httplib2 transports cannot be shared by workers.
                service = get_gmail_service(user_email)
                body = await asyncio.to_thread(_get_email_body, service, email_id)

            # URL cache rows reference analyzed_emails. Pending never means analyzed.
            if not update_mode:
                persist(label_id=None, scam_score=None, scam_indicators="[]", is_quarantined=0,
                        status="fetched", received_at=received_at, analysis_status="pending")

            urls = list(dict.fromkeys(extract_urls(body)))
            urls_total = len(urls)
            selected_urls = urls[:10]
            scan_results = await asyncio.gather(*[
                scan_url(url, email_id, url_client, url_semaphore) for url in selected_urls
            ], return_exceptions=True)
            url_scan_unavailable = len(selected_urls) < urls_total
            scan_failure_reasons = set()
            for result in scan_results:
                if isinstance(result, BaseException):
                    scan_failure_reasons.add("safe_browsing_request_error")
                    url_scan_unavailable = True
                    continue
                if result.get("scan_failed") or result.get("is_safe") is None:
                    scan_failure_reasons.add(result.get("reason") or "safe_browsing_request_error")
                    url_scan_unavailable = True
                    continue
                urls_checked += 1
                if result.get("is_safe") == 0 and result.get("threat_type"):
                    url_threat_confirmed = True
            if scan_failure_reasons:
                logger.warning(
                    "[PIPELINE] URL scan unavailable for email %s: %s",
                    email_id[:12],
                    ", ".join(sorted(scan_failure_reasons)),
                )
            url_scan_status = (
                "threat_detected" if url_threat_confirmed else
                "not_applicable" if not urls_total else
                "unavailable" if not urls_checked else
                "partial" if url_scan_unavailable else "completed"
            )

            # Phase 5: Attachment scanning
            from attachment_scanner import scan_attachments
            attachment_verdict = "clean"
            attachment_scam_adjustment = 0
            attachment_details = None
            
            # Extract attachments from email payload (Gmail API format)
            attachments_info = []
            if "payload" in email and "parts" in email["payload"]:
                for part in email["payload"]["parts"]:
                    if part.get("filename"):
                        attachments_info.append({
                            "filename": part["filename"],
                            "size": part.get("body", {}).get("size", 0)
                        })
            
            # Scan attachments if present
            if attachments_info:
                attachment_scan_result = scan_attachments(attachments_info)
                attachment_verdict = attachment_scan_result["overall_verdict"]
                attachment_scam_adjustment = attachment_scan_result["total_scam_score_adjustment"]
                attachment_details = json.dumps(attachment_scan_result)
                
                logger.info(
                    f"[ATTACHMENT] {email_id[:12]}: {len(attachments_info)} attachments, "
                    f"verdict={attachment_verdict}, adjustment=+{attachment_scam_adjustment}"
                )

            from v2_routing import route_email_with_v2

            async def run_ai_cascade():
                prompt = classification_prompt.format(
                    sender=sender, subject=subject, body=_analysis_text(body)[:6000],
                    url_threat_confirmed=url_threat_confirmed,
                    url_scan_unavailable=url_scan_unavailable,
                    available_labels=", ".join(available_label_names),
                )
                return await ai_router.analyze_json(prompt)

            routed = await route_email_with_v2(
                email_id=email_id, subject=subject, sender=sender, body=body, snippet=snippet,
                ai_cascade_func=run_ai_cascade, classification_prompt=classification_prompt,
                url_threat_confirmed=url_threat_confirmed, url_scan_unavailable=url_scan_unavailable,
                available_label_names=available_label_names,
            )
            label = routed.get("label", "Unknown")
            match = next((name for name in available_label_names
                          if isinstance(label, str) and name.casefold() == label.strip().casefold()), None)
            if not match:
                logger.warning(
                    "[PIPELINE] AI label unavailable for email %s: returned=%r available=%s",
                    email_id[:12],
                    label,
                    available_label_names,
                )
            category_status = routed.get("category_status", "completed" if match else "unavailable")
            if category_status == "complete":
                category_status = "completed"
            label = match if match and category_status == "completed" else "Unknown"
            label_id = get_label_id_by_name(user_id, label) if label != "Unknown" else None
            score = routed.get("scam_score")
            if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
                raise ValueError("No valid security assessment")
            indicators = routed.get("scam_indicators", [])
            if not isinstance(indicators, list) or not all(isinstance(i, str) for i in indicators):
                raise ValueError("Invalid evidence format")
            if url_threat_confirmed:
                score = max(score, 95)
                if "Known malicious link detected" not in indicators:
                    indicators = [*indicators, "Known malicious link detected"]
            
            # Phase 5: Apply attachment risk adjustment to scam score
            if attachment_scam_adjustment > 0:
                score = min(score + attachment_scam_adjustment, 100)
                if attachment_verdict == "malicious":
                    if "Malicious attachment detected" not in indicators:
                        indicators = [*indicators, "Malicious attachment detected"]
                elif attachment_verdict == "suspicious":
                    if "Suspicious attachment detected" not in indicators:
                        indicators = [*indicators, "Suspicious attachment detected"]
            
            analysis_status = _final_analysis_status(
                routed.get("analysis_status", "completed"), url_scan_unavailable, label_id
            )
            decision = routed.get("routing_decision", "unknown")
            v2_score = routed.get("v2_score")
            provider_used = routed.get("provider_used")
            if not provider_used and v2_score is not None:
                provider_used = "local_ml_v2"
            # This flag is a local review queue, not isolation in Gmail.
            quarantine = int(url_threat_confirmed or score >= 70)
            persist(
                label_id=label_id, scam_score=score, scam_indicators=json.dumps(indicators),
                is_quarantined=quarantine, status="labeled",
                source="v2" if decision.startswith("v2_") else "ai", ml_confidence=None,
                v2_score=v2_score, provider_used=provider_used,
                reasoning=routed.get("reasoning", ""), routing_decision=decision,
                analysis_status=analysis_status, category_status=category_status,
                url_scan_status=url_scan_status, urls_total=urls_total, urls_checked=urls_checked,
                received_at=received_at,
                attachment_risk=attachment_verdict,  # Phase 5: clean, suspicious, malicious
                attachment_details=attachment_details,  # Phase 5: JSON scan results
            )
            remove_from_retry_queue(email_id)
            return {**base, "label": label, "scam_score": score, "is_quarantined": quarantine,
                    "status": "success", "analysis_status": analysis_status,
                    "category_status": category_status, "url_scan_status": url_scan_status,
                    "urls_total": urls_total, "urls_checked": urls_checked, "sync_status": "pending"}
        except Exception as error:
            import traceback
            logger.error("[PIPELINE] Analysis failed for %s: %s", email_id[:12], type(error).__name__)
            logger.error("[PIPELINE] Exception details: %s", str(error))
            logger.error("[PIPELINE] Traceback:\n%s", traceback.format_exc())
            # Preserve confirmed external evidence even if later processing fails.
            score = 95 if url_threat_confirmed else None
            indicators = ["Known malicious link detected"] if url_threat_confirmed else []
            try:
                persist(label_id=None, scam_score=score, scam_indicators=json.dumps(indicators),
                        is_quarantined=int(url_threat_confirmed), status="failed", source=None,
                        analysis_status="failed", category_status="unavailable",
                        url_scan_status=url_scan_status, urls_total=urls_total, urls_checked=urls_checked,
                        received_at=received_at)
                add_to_retry_queue(email_id, user_id, "Analysis unavailable; retry required")
            except Exception as save_error:
                logger.error("[PIPELINE] Could not persist failure: %s", type(save_error).__name__)
            return {**base, "label": "Unknown", "scam_score": score,
                    "is_quarantined": int(url_threat_confirmed), "status": "failed",
                    "analysis_status": "failed", "error": "Analysis unavailable — retry."}



# ---------- LEGACY BULK ANALYSIS (kept for backward compat) ----------

async def analyze_bulk(limit: int = 50, user_id: int = None):
    async for event in analyze_bulk_ordered(limit=limit, user_id=user_id):
        yield event


# ---------- DECOUPLED FETCH/LABEL PIPELINES (Phase 24) ----------

async def fetch_only_pipeline(limit: int = 50, user_id: int = None, user_email: str = None):
    """
    Fetch emails from Gmail and save as status='fetched' placeholders.
    No URL scanning, no AI analysis. Yields SSE progress events.
    """
    if user_email is None and user_id is not None:
        user_email = get_user_email_by_id(user_id)

    service = get_gmail_service(user_email)
    if not service or user_id is None:
        yield {"type": "complete", "fetched": 0, "skipped": 0, "error": "Not authenticated"}
        return

    yield {"type": "initializing", "message": "Fetching emails from Gmail..."}

    try:
        new_emails, skipped_count, _ = await _fetch_new_emails(limit, user_id, user_email)
    except Exception as e:
        yield {"type": "complete", "fetched": 0, "error": "An internal error occurred during analysis."}
        return

    saved_count = 0
    for email in new_emails:
        try:
            # Fetch full body before saving (metadata fetch returns body="")
            body = email.get("body", "")
            if not body:
                body = await asyncio.to_thread(_get_email_body, service, email["id"])
            
            save_analyzed_email(
                email_id=email["id"],
                user_id=user_id,
                label_id=None,
                scam_score=None,
                scam_indicators='[]',
                is_quarantined=0,
                snippet=email.get("snippet", ""),
                sender=email.get("sender", ""),
                subject=email.get("subject", ""),
                status='fetched',
                body=body,
            )
            saved_count += 1
            yield {"type": "progress", "current": saved_count, "total": len(new_emails)}
        except Exception as e:
            logger.info(f"[FETCH-ONLY] Failed to save {email['id']}: {e}")
            continue

    yield {"type": "complete", "fetched": saved_count, "skipped": skipped_count}


async def label_only_pipeline(limit: int = None, user_id: int = None, user_email: str = None, email_ids: list[str] = None):
    """
    Read status='fetched' emails from DB and run AI analysis.
    Updates rows to status='labeled'. Yields SSE progress events.
    
    Args:
        limit: Max number of emails to fetch (ignored if email_ids provided)
        user_id: User ID for ownership check
        user_email: User's email address
        email_ids: Optional list of specific email IDs to process (exact retry targets)
    """
    from ai_router import ai_router, CLASSIFICATION_PROMPT
    from database import get_emails_by_status, get_emails_by_ids
    import httpx

    if user_email is None and user_id is not None:
        user_email = get_user_email_by_id(user_id)

    semaphore = asyncio.Semaphore(2)
    url_semaphore = asyncio.Semaphore(8)
    service = get_gmail_service(user_email)

    if not service or user_id is None:
        yield {"type": "complete", "analyzed": 0, "failed": 0, "error": "Not authenticated"}
        return

    gmail_labels_result = await asyncio.to_thread(
        lambda: service.users().labels().list(userId="me").execute()
    )
    gmail_labels_cache = {
        lbl["name"]: lbl["id"] for lbl in gmail_labels_result.get("labels", [])
    }

    # Cache labels once per bulk run (instead of per-email DB query)
    available_labels_list = await asyncio.to_thread(get_labels, user_id)
    available_label_names = [lbl["label_name"] for lbl in available_labels_list]
    
    if not available_label_names:
        logger.warning(f"[PIPELINE] Empty label list for user_id={user_id} — analysis will produce unavailable category_status")

    async with httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=50)) as url_client:
        yield {"type": "initializing", "message": "Starting AI analysis..."}

        # P0-4 fix: Use exact email_ids when provided (retry endpoint)
        if email_ids:
            fetched_emails = get_emails_by_ids(user_id, email_ids)
        else:
            fetched_emails = get_emails_by_status(user_id, status='fetched', limit=limit)

        if not fetched_emails:
            yield {"type": "complete", "analyzed": 0, "failed": 0}
            return

        total = len(fetched_emails)
        yield {"type": "progress", "current": 0, "total": total}

        tasks = [
            asyncio.create_task(_analyze_one(
                email=email,
                semaphore=semaphore,
                ai_router=ai_router,
                classification_prompt=CLASSIFICATION_PROMPT,
                user_id=user_id,
                user_email=user_email,
                service=service,
                url_client=url_client,
                url_semaphore=url_semaphore,
                available_label_names=available_label_names,
                gmail_labels_cache=gmail_labels_cache,
                update_mode=True,
            ))
            for email in fetched_emails
        ]

        done_queue = asyncio.Queue()
        
        async def track_completion(task, idx):
            result = await task
            await done_queue.put((idx, result))
        
        tracking_tasks = [asyncio.create_task(track_completion(t, i)) for i, t in enumerate(tasks)]
        
        analyzed_count = 0
        failed_count = 0
        results = []
        
        for _ in range(len(tasks)):
            idx, result = await done_queue.get()
            
            if result.get("status") == "failed":
                failed_count += 1
            elif result.get("status") == "success":
                analyzed_count += 1
                results.append(result)
            
            yield {
                "type": "email_done",
                "current": analyzed_count + failed_count,
                "total": total,
                "email_id": result.get("email_id"),
                "subject": result.get("subject"),
                "label": result.get("label", ""),
                "scam_score": result.get("scam_score", 0),
            }
        
        await asyncio.gather(*tracking_tasks)
        
        yield {"type": "complete", "analyzed": analyzed_count, "failed": failed_count, "results": results}

