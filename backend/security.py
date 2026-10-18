"""
security.py — Security Scanner Module (Restructured)
Contains exactly two functions:
  1. extract_urls — Extract URLs from plain text and HTML
  2. scan_url — Check URL safety via Google Safe Browsing API with caching
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import re
import httpx
import asyncio
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Google Safe Browsing API key from .env
SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")
URL_SAFETY_CACHE: dict[str, tuple[int, str | None]] = {}
_cache_lock = asyncio.Lock()  # Protects URL_SAFETY_CACHE from concurrent access
URL_CHECK_TIMEOUT_SECONDS = 5.0  # Legacy scan_url() timeout (deprecated)
BATCH_SCAN_TIMEOUT = 8.0  # Phase 3 Task 10: Batch scan timeout


def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs starting with http:// or https:// from plain text using regex.
    Also extract href attribute values from HTML anchor tags using BeautifulSoup
    if the text contains HTML.
    Also detect anchor mismatch: if visible link text and href point to different
    domains, include the href URL in the result with a note.
    Deduplicate the list before returning.

    Args:
        text: Raw email body (plain text or HTML)

    Returns:
        Deduplicated list of URL strings
    """
    urls = set()

    # Step 1: Regex for http/https URLs in plain text
    url_pattern = r'https?://[^\s<>"\')\];}]+'
    plain_urls = re.findall(url_pattern, text)
    for url in plain_urls:
        # Clean trailing punctuation
        url = url.rstrip(".,;:!?)")
        urls.add(url)

    # Step 2: Extract href values from HTML anchor tags using BeautifulSoup
    if "<a " in text.lower() or "<a>" in text.lower():
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"]
                if href.startswith("http://") or href.startswith("https://"):
                    urls.add(href)

                    # Step 3: Anchor mismatch detection
                    anchor_text = anchor.get_text(strip=True)
                    if anchor_text.startswith("http://") or anchor_text.startswith("https://"):
                        # Visible text looks like a URL — compare domains
                        href_domain = _extract_domain(href)
                        text_domain = _extract_domain(anchor_text)
                        if href_domain and text_domain and href_domain != text_domain:
                            # Mismatch: anchor text shows one domain but links to another
                            logger.info(f"[SECURITY] WARNING: Anchor mismatch: shows '{text_domain}' but links to '{href_domain}'")
                            urls.add(href)  # Ensure the actual href is in the result
        except ImportError:
            logger.info("[SECURITY] BeautifulSoup not installed, skipping HTML anchor extraction")

    result = list(urls)
    logger.info(f"[SECURITY] Extracted {len(result)} URLs from email body.")
    return result


def _extract_domain(url: str) -> str | None:
    """Extract the domain from a URL. Returns None if extraction fails."""
    try:
        parsed = urlparse(url)
        domain = parsed.hostname
        if domain and domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return None


async def scan_urls_batch(urls: list[str], email_id: str,
                          client: httpx.AsyncClient,
                          api_key: str = None) -> dict[str, dict]:
    """
    Check multiple URLs against Google Safe Browsing API v4 in a single batch request.
    
    Phase 3 (Tasks 10-11): Replaces one-request-per-URL with batched threatMatches:find.
    - Single API request with all deduped URLs in threatEntries[] (cap 500)
    - 8s timeout (up from 5s)
    - 1 retry with jitter on timeout/5xx
    - Cache checked before batch, saved after
    - Never cache failed scans as safe
    - Scan failures do NOT downgrade analysis_status
    
    Args:
        urls: List of URLs to check (will be deduped)
        email_id: Gmail message ID for cache association
        client: Shared httpx.AsyncClient
    
    Returns:
        Dict mapping each URL to result dict with keys:
        - url: the URL
        - is_safe: 0=unsafe, 1=safe, None=scan_failed
        - threat_type: threat name if unsafe, else None
        - scan_failed: bool
    """
    from database import get_cached_url, save_url_result
    
    if not urls:
        return {}
    
    # Dedupe and cap at 500 (Safe Browsing API limit)
    unique_urls = list(dict.fromkeys(urls))[:500]
    
    # Step 1: Check cache for ALL URLs first
    results = {}
    uncached_urls = []
    mem_hits = 0
    db_hits = 0
    
    for url in unique_urls:
        # Check in-memory cache first (fast path)
        async with _cache_lock:
            cached_result = URL_SAFETY_CACHE.get(url)
            if cached_result is not None:
                mem_hits += 1
                logger.debug(f"[SECURITY] In-memory cache hit: {url[:60]}")
                results[url] = {
                    "url": url,
                    "is_safe": cached_result[0],
                    "threat_type": cached_result[1],
                    "scan_failed": False
                }
                continue
        
        # Check persistent cache (offload to thread)
        cached = await asyncio.to_thread(get_cached_url, url)
        if cached is not None:
            db_hits += 1
            logger.debug(f"[SECURITY] DB cache hit: {url[:60]}")
            results[url] = {
                "url": url,
                "is_safe": cached["is_safe"],
                "threat_type": cached["threat_type"],
                "scan_failed": False
            }
            # Warm in-memory cache
            async with _cache_lock:
                URL_SAFETY_CACHE[url] = (cached["is_safe"], cached["threat_type"])
        else:
            uncached_urls.append(url)
    
    if unique_urls:
        logger.info(f"[SECURITY] URL cache: {len(unique_urls)} total, {mem_hits} memory hits, {db_hits} db hits, {len(uncached_urls)} to scan")

    if not uncached_urls:
        logger.info(f"[SECURITY] All {len(unique_urls)} URLs cached, no API call needed")
        return results
    
    # Step 2: API key check
    key_to_use = api_key or SAFE_BROWSING_KEY
    if not key_to_use or key_to_use == "your_key_here":
        logger.info(f"[SECURITY] WARNING: Safe Browsing API key not configured. {len(uncached_urls)} URLs unavailable")
        for url in uncached_urls:
            results[url] = {
                "url": url,
                "is_safe": None,
                "threat_type": None,
                "scan_failed": True,
                "verdict": "unavailable",
                "reason": "safe_browsing_not_configured"
            }
        return results
    
    # Step 3: Build batch request
    endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    headers = {"x-goog-api-key": key_to_use}
    body = {
        "client": {
            "clientId": "gmail-manager",
            "clientVersion": "1.0",
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url} for url in uncached_urls],
        },
    }
    
    logger.info(f"[SECURITY] Batch scanning {len(uncached_urls)} uncached URLs (timeout {BATCH_SCAN_TIMEOUT}s, 1 retry)")
    
    # Step 4: Call API with retry (timeout/5xx only)
    MAX_ATTEMPTS = 2  # 1 retry = 2 total attempts
    
    response = None
    last_exception = None
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.post(
                endpoint,
                json=body,
                headers=headers,
                timeout=BATCH_SCAN_TIMEOUT,
            )
            
            if response.status_code == 200:
                break  # Success
            
            # Non-200: retry on 5xx, fail on 4xx
            if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
                jitter = random.uniform(0.1, 0.5)
                logger.info(f"[SECURITY] Batch scan HTTP {response.status_code}, retry {attempt}/{MAX_ATTEMPTS-1} after {jitter:.2f}s")
                await asyncio.sleep(jitter)
                continue
            else:
                # 4xx or final attempt
                last_exception = f"HTTP_{response.status_code}"
                break
                
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            if attempt < MAX_ATTEMPTS:
                jitter = random.uniform(0.1, 0.5)
                logger.info(f"[SECURITY] Batch scan timeout, retry {attempt}/{MAX_ATTEMPTS-1} after {jitter:.2f}s")
                await asyncio.sleep(jitter)
                last_exception = "TIMEOUT"
            else:
                last_exception = "TIMEOUT"
                break
        except Exception as e:
            logger.error(f"[SECURITY] Batch scan exception: {type(e).__name__}: {e}")
            last_exception = type(e).__name__
            break
    
    # Step 5: Parse response
    if response and response.status_code == 200:
        try:
            data = response.json()
            matches = data.get("matches", [])
            
            # Build URL->threat map
            threat_map = {}
            for match in matches:
                url = match.get("threat", {}).get("url")
                threat_type = match.get("threatType", "UNKNOWN")
                if url:
                    threat_map[url] = threat_type
            
            # Assign verdicts
            for url in uncached_urls:
                if url in threat_map:
                    # Threat confirmed
                    is_safe = 0
                    threat_type = threat_map[url]
                    logger.info(f"[SECURITY] UNSAFE: {url[:60]} - {threat_type}")
                else:
                    # No match = safe
                    is_safe = 1
                    threat_type = None
                
                results[url] = {
                    "url": url,
                    "is_safe": is_safe,
                    "threat_type": threat_type,
                    "scan_failed": False
                }
                
                # Cache verdicts (not failures)
                async with _cache_lock:
                    URL_SAFETY_CACHE[url] = (is_safe, threat_type)
                await asyncio.to_thread(save_url_result, email_id, url, is_safe, threat_type)
            
            logger.info(f"[SECURITY] Batch scan OK: {len(uncached_urls)} URLs, {len(threat_map)} threats")
            
        except Exception as e:
            logger.error(f"[SECURITY] Failed to parse batch response: {e}")
            # Treat as scan_failed for all uncached URLs
            for url in uncached_urls:
                results[url] = {
                    "url": url,
                    "is_safe": None,
                    "threat_type": None,
                    "scan_failed": True
                }
    else:
        # API call failed
        logger.error(f"[SECURITY] Batch scan failed: {last_exception}")
        for url in uncached_urls:
            results[url] = {
                "url": url,
                "is_safe": None,
                "threat_type": None,
                "scan_failed": True
            }
    
    return results


async def scan_url(url: str, email_id: str,
                   client: httpx.AsyncClient,
                   semaphore: asyncio.Semaphore) -> dict:
    """
    Check a URL against the Google Safe Browsing API v4 with caching.

    First calls get_cached_url(url) — if cached and within 24 hours, returns immediately.
    If not cached, calls the Safe Browsing API v4 threatMatches:find endpoint.
    Checks three threat types: MALWARE, SOCIAL_ENGINEERING, UNWANTED_SOFTWARE.
    Saves the result via save_url_result() for future cache hits.

    Args:
        url: The URL to check
        email_id: The Gmail message ID (for cache association)
        client: Shared httpx.AsyncClient for pooled connections
        semaphore: asyncio.Semaphore to cap concurrency

    Returns:
        Dict with keys: url, is_safe (int), threat_type (str or None)
    """
    from database import get_cached_url, save_url_result

    # Step 1: Check cache first (offload blocking DB call to thread)
    cached = await asyncio.to_thread(get_cached_url, url)
    if cached is not None:
        logger.debug(f"[SECURITY] Cache hit for URL: {url[:60]}")
        return {
            "url": url,
            "is_safe": cached["is_safe"],
            "threat_type": cached["threat_type"],
        }

    # Step 2: No persistent cache — use the in-memory cache for this process.
    # Lock protects against cache stampede (multiple tasks checking same URL concurrently)
    async with _cache_lock:
        cached_result = URL_SAFETY_CACHE.get(url)
        if cached_result is not None:
            logger.debug(f"[SECURITY] In-memory cache hit for URL: {url[:60]}")
            return {"url": url, "is_safe": cached_result[0], "threat_type": cached_result[1]}

    # Step 3: No cache — call Google Safe Browsing API v4
    if not SAFE_BROWSING_KEY or SAFE_BROWSING_KEY == "your_key_here":
        logger.info(f"[SECURITY] WARNING: Safe Browsing API key not configured. URL scan unavailable for: {url[:60]}")
        # Return unavailable verdict, never cache as safe
        return {
            "url": url,
            "is_safe": None,  # None = scan unavailable, not safe
            "threat_type": None,
            "scan_failed": True,
            "verdict": "unavailable",
            "reason": "safe_browsing_not_configured"
        }

    endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    headers = {"x-goog-api-key": SAFE_BROWSING_KEY}
    body = {
        "client": {
            "clientId": "gmail-manager",
            "clientVersion": "1.0",
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    # Three-state result: None = scan_failed, 0 = verdict_unsafe, 1 = verdict_safe
    # Using None instead of is_safe=0 prevents conflating "API error" with "confirmed threat"
    is_safe = None  # Default to None when scan hasn't completed yet
    threat_type = None
    scan_failed = False

    exception_type = None
    exception_message = None
    response_status = None
    response_body = None
    
    try:
        async with semaphore:
            response = await client.post(
                endpoint,
                json=body,
                headers=headers,
                timeout=URL_CHECK_TIMEOUT_SECONDS,
            )
        
        response_status = response.status_code

        if response.status_code != 200:
            # Capture response body for diagnosis
            try:
                response_body = response.text[:500]  # First 500 chars
            except:
                response_body = "<unable to read response body>"
            
            logger.info(f"[SECURITY] Safe Browsing API error: {response.status_code}")
            logger.info(f"[SECURITY] Response body: {response_body}")
            
            # Check for specific error types
            if response.status_code == 429:
                logger.info(f"[SECURITY] DIAGNOSIS: Rate limit / quota exceeded (HTTP 429)")
                exception_type = "RATE_LIMIT"
                exception_message = f"HTTP 429: {response_body}"
            elif response.status_code == 400:
                logger.info(f"[SECURITY] DIAGNOSIS: Bad request / malformed URL (HTTP 400)")
                exception_type = "BAD_REQUEST"
                exception_message = f"HTTP 400: {response_body}"
            elif response.status_code >= 500:
                logger.info(f"[SECURITY] DIAGNOSIS: Server error (HTTP {response.status_code})")
                exception_type = "SERVER_ERROR"
                exception_message = f"HTTP {response.status_code}: {response_body}"
            else:
                exception_type = f"HTTP_{response.status_code}"
                exception_message = response_body
            
            scan_failed = True
        else:
            data = response.json()
            if data.get("matches"):
                is_safe = 0  # verdict_unsafe: API confirmed threat
                threat_type = data["matches"][0].get("threatType", "UNKNOWN")
                logger.info(f"[SECURITY] WARNING: UNSAFE URL detected: {url[:60]} - {threat_type}")
            else:
                # API returned 200 with no matches = safe
                is_safe = 1  # verdict_safe: API confirmed safe

    except asyncio.TimeoutError as e:
        import traceback
        exception_type = "TIMEOUT"
        exception_message = f"Timeout after {URL_CHECK_TIMEOUT_SECONDS}s"
        logger.info(f"[SECURITY] DIAGNOSIS: Timeout checking URL {url[:60]}")
        logger.info(f"[SECURITY] Timeout value: {URL_CHECK_TIMEOUT_SECONDS}s")
        logger.info(f"[SECURITY] Full traceback:\n{traceback.format_exc()}")
        scan_failed = True
    except httpx.TimeoutException as e:
        import traceback
        exception_type = "TIMEOUT"
        exception_message = f"httpx.TimeoutException: {str(e)}"
        logger.info(f"[SECURITY] DIAGNOSIS: httpx Timeout checking URL {url[:60]}")
        logger.info(f"[SECURITY] Timeout value: {URL_CHECK_TIMEOUT_SECONDS}s")
        logger.info(f"[SECURITY] Exception details: {e!r}")
        logger.info(f"[SECURITY] Full traceback:\n{traceback.format_exc()}")
        scan_failed = True
    except httpx.HTTPStatusError as e:
        import traceback
        exception_type = "HTTP_ERROR"
        exception_message = f"HTTPStatusError: {e.response.status_code}"
        response_status = e.response.status_code
        logger.info(f"[SECURITY] DIAGNOSIS: HTTP status error for {url[:60]}: {e.response.status_code}")
        logger.info(f"[SECURITY] Full traceback:\n{traceback.format_exc()}")
        scan_failed = True
    except Exception as e:
        import traceback
        exception_type = type(e).__name__
        exception_message = str(e)
        logger.info(f"[SECURITY] DIAGNOSIS: {exception_type} checking URL {url[:60]}: {e!r}")
        logger.info(f"[SECURITY] Full traceback:\n{traceback.format_exc()}")
        scan_failed = True

    # Step 4: Save results to persistent and in-memory caches.
    # Only cache actual verdicts (is_safe = 0 or 1), not scan failures (is_safe = None)
    if is_safe is not None:
        async with _cache_lock:
            URL_SAFETY_CACHE[url] = (is_safe, threat_type)
        # Offload blocking DB call to thread to prevent event loop blocking
        await asyncio.to_thread(save_url_result, email_id, url, is_safe, threat_type)
    else:
        logger.info(f"[SECURITY] Scan failed for {url[:60]}, not caching result")
        # Log scan failure for diagnosis (Step 4 of task)
        await _log_scan_failure(url, email_id, exception_type, exception_message, response_status)

    return {
        "url": url, 
        "is_safe": is_safe,  # None = scan_failed, 0 = verdict_unsafe, 1 = verdict_safe
        "threat_type": threat_type,
        "scan_failed": scan_failed
    }


async def _log_scan_failure(url: str, email_id: str, exception_type: str, exception_message: str, response_status: int):
    """
    Log scan failures for visibility and diagnosis.
    Writes to console and attempts to persist to database for queryable history.
    """
    from datetime import datetime
    timestamp = datetime.utcnow().isoformat()
    
    logger.error(f"[SECURITY] SCAN_FAILURE_LOG | {timestamp} | {exception_type} | {url[:80]} | {exception_message[:200]}")
    
    # Attempt to save to database for queryable record
    try:
        from database import _get_connection, _execute, _release_connection
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if scan_failures table exists, create if not
            _execute(cursor, """
                CREATE TABLE IF NOT EXISTS scan_failures (
                    failure_id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    url TEXT NOT NULL,
                    email_id TEXT,
                    exception_type TEXT,
                    exception_message TEXT,
                    response_status INTEGER
                )
            """)
            
            # Insert failure record
            _execute(cursor, """
                INSERT INTO scan_failures (url, email_id, exception_type, exception_message, response_status)
                VALUES (%s, %s, %s, %s, %s)
            """, (url, email_id, exception_type, exception_message, response_status))
            
            conn.commit()
        except Exception as db_err:
            logger.info(f"[SECURITY] Warning: Could not persist scan failure to database: {db_err}")
        finally:
            _release_connection(conn)
    except Exception as e:
        # Don't let logging failures break the main flow
        logger.info(f"[SECURITY] Warning: Failed to log scan failure: {e}")
