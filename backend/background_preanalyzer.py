import os
import json
import re
import asyncio
import time
import httpx
from logger_setup import get_logger
from ai_router import CLASSIFICATION_PROMPT, match_label
from security import extract_urls, scan_urls_batch
from database import (
    get_unpreanalyzed_emails,
    update_prefetched_email,
    get_labels,
    get_label_id_by_name,
)
from quarantine_policy import should_quarantine

logger = get_logger(__name__)

PRIMARY_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
FALLBACK_MODEL = "liquid/lfm-2.5-2.6b:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Global pause lock: cleared when user triggers manual analysis, set when idle/manual completes
_pause_event = asyncio.Event()
_pause_event.set()

# Track running preanalyzer tasks per user: {user_id: asyncio.Task}
_active_user_tasks: dict[int, asyncio.Task] = {}
_tasks_lock = asyncio.Lock()


def get_background_openrouter_keys() -> list[str]:
    """
    Load OpenRouter API keys from environment.
    Primary format: OPENROUTER_BACKGROUND_KEYS=key1,key2,... (comma-separated)
    Fallback: Numbered keys OPENROUTER_BACKGROUND_KEYS1..30, KEY_1, etc.
    """
    raw = os.getenv("OPENROUTER_BACKGROUND_KEYS", "").strip()
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        for i in range(1, 31):
            k = (
                os.getenv(f"OPENROUTER_BACKGROUND_KEYS{i}")
                or os.getenv(f"OPENROUTER_BACKGROUND_KEY_{i}")
                or os.getenv(f"OPENROUTER_BACKGROUND_KEY{i}")
            )
            if k and k.strip():
                keys.append(k.strip())
    return keys


def get_background_safebrowsing_key() -> str | None:
    """
    Load dedicated Safe Browsing API key for background workers.
    Falls back to GOOGLE_SAFE_BROWSING_KEY if not explicitly set.
    """
    return os.getenv("BACKGROUND_SAFE_BROWSING_API_KEY") or os.getenv("GOOGLE_SAFE_BROWSING_KEY")


def pause_preanalyzer():
    """Immediately pause background workers to prevent conflicts during manual user analysis."""
    _pause_event.clear()
    logger.info("[PREANALYZER] Background workers PAUSED due to active user analysis")


def resume_preanalyzer():
    """Resume background workers once manual user analysis finishes."""
    _pause_event.set()
    logger.info("[PREANALYZER] Background workers RESUMED")


def is_preanalyzer_paused() -> bool:
    """Return True if background workers are paused."""
    return not _pause_event.is_set()


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


async def call_openrouter_single(
    client: httpx.AsyncClient,
    api_key: str,
    prompt: str,
    model: str,
) -> dict:
    """
    Call OpenRouter chat completion endpoint with a specific model.
    Returns parsed dictionary with label, scam_score, scam_indicators, reasoning.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://gmail-manager.app",
        "X-Title": "Gmail Manager Background Preanalyzer",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }

    response = await client.post(OPENROUTER_URL, headers=headers, json=payload, timeout=25.0)
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}: {response.text[:250]}")

    data = response.json()
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError(f"Unexpected response structure from {model}")

    content = choices[0].get("message", {}).get("content", "")
    cleaned = _clean_json_text(content)
    parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise ValueError("Model response is not a valid JSON dictionary")

    if "label" not in parsed or "scam_score" not in parsed:
        raise ValueError(f"Missing required fields ('label', 'scam_score') from {model}")

    score = parsed.get("scam_score")
    if score is not None and not isinstance(score, bool):
        try:
            parsed["scam_score"] = int(round(float(score)))
        except (ValueError, TypeError):
            parsed["scam_score"] = 0
    else:
        parsed["scam_score"] = 0

    if not isinstance(parsed.get("scam_indicators"), list):
        parsed["scam_indicators"] = []

    if not isinstance(parsed.get("reasoning"), str):
        parsed["reasoning"] = str(parsed.get("reasoning") or "")

    return parsed


async def call_openrouter_with_failover(
    client: httpx.AsyncClient,
    api_key: str,
    prompt: str,
) -> tuple[dict, str]:
    """
    Model Strategy:
    1. Try Primary: nvidia/nemotron-3-ultra-550b-a55b:free (fastest total time, 550B quality)
    2. If fails, failover to Fallback: liquid/lfm-2.5-2.6b:free (fastest TTFT)
    """
    # Attempt 1: Nemotron Ultra
    try:
        result = await call_openrouter_single(client, api_key, prompt, PRIMARY_MODEL)
        return result, PRIMARY_MODEL
    except Exception as nemotron_err:
        logger.warning(
            f"[PREANALYZER] Primary model ({PRIMARY_MODEL}) failed: {nemotron_err}. "
            f"Failing over to ({FALLBACK_MODEL})..."
        )

    # Attempt 2: Liquid LFM
    try:
        result = await call_openrouter_single(client, api_key, prompt, FALLBACK_MODEL)
        return result, FALLBACK_MODEL
    except Exception as liquid_err:
        logger.warning(f"[PREANALYZER] Fallback model ({FALLBACK_MODEL}) also failed: {liquid_err}")
        raise


async def _worker_loop(
    worker_idx: int,
    api_key: str,
    queue: asyncio.Queue,
    user_id: int,
    available_label_names: list[str],
    label_id_by_name: dict[str, int],
    safebrowsing_key: str | None,
    client: httpx.AsyncClient,
):
    """
    Single background worker coroutine tied to a dedicated OpenRouter API key.
    Pulls from the shared queue, processes Safe Browsing + AI with failover,
    saves pre-analyzed result to DB, and immediately pulls the next email.
    """
    while True:
        # Pause shield: wait if user clicked Analyze
        await _pause_event.wait()

        try:
            email = await asyncio.wait_for(queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            # Queue exhausted
            break

        email_id = email.get("email_id") or email.get("id")
        try:
            # Check pause again before initiating network call
            await _pause_event.wait()

            body = email.get("body", "")
            subject = email.get("subject", "(No Subject)")
            sender = email.get("sender", "(Unknown)")
            received_at = email.get("received_at")

            # Step 1: Scan URLs via dedicated Safe Browsing key
            url_threat_confirmed = False
            url_scan_unavailable = False
            urls_total = urls_checked = 0
            url_scan_status = "not_applicable"

            if body:
                urls = list(dict.fromkeys(await asyncio.to_thread(extract_urls, body)))
                urls_total = len(urls)
                if urls:
                    selected_urls = urls[:30]
                    try:
                        scan_results = await scan_urls_batch(
                            selected_urls,
                            email_id,
                            client,
                            api_key=safebrowsing_key,
                        )
                        url_scan_unavailable = len(selected_urls) < urls_total
                        for u, res in scan_results.items():
                            if res.get("scan_failed") or res.get("is_safe") is None:
                                url_scan_unavailable = True
                                continue
                            urls_checked += 1
                            if res.get("is_safe") == 0 and res.get("threat_type"):
                                url_threat_confirmed = True

                        url_scan_status = (
                            "threat_detected" if url_threat_confirmed else
                            "unavailable" if not urls_checked else
                            "partial" if url_scan_unavailable else "completed"
                        )
                    except Exception as scan_err:
                        logger.warning(f"[PREANALYZER Worker {worker_idx}] URL scan error for {email_id}: {scan_err}")
                        url_scan_unavailable = True
                        url_scan_status = "unavailable"

            # Step 2: Prepare classification prompt
            # Extract plain text preview
            from gmail import _analysis_text
            preview_body = _analysis_text(body)[:6000]

            prompt = CLASSIFICATION_PROMPT.format(
                sender=sender,
                subject=subject,
                body=preview_body,
                url_threat_confirmed=url_threat_confirmed,
                url_scan_unavailable=url_scan_unavailable,
                available_labels=", ".join(available_label_names),
            )

            # Step 3: Run AI with failover (Nemotron -> Liquid)
            ai_data, model_used = await call_openrouter_with_failover(client, api_key, prompt)

            raw_label = ai_data.get("label", "")
            matched_label = match_label(raw_label, available_label_names) or "Unknown"
            label_id = label_id_by_name.get(matched_label.casefold())

            score = ai_data.get("scam_score", 0)
            if url_threat_confirmed:
                score = max(score, 95)

            indicators = ai_data.get("scam_indicators", [])
            if url_threat_confirmed and "Known malicious link detected" not in indicators:
                indicators.append("Known malicious link detected")

            quarantined = int(should_quarantine(score, url_threat_confirmed, matched_label))

            # Step 4: Persist to prefetched_emails staging table
            await asyncio.to_thread(
                update_prefetched_email,
                email_id=email_id,
                label_id=label_id,
                scam_score=score,
                scam_indicators=json.dumps(indicators),
                is_quarantined=quarantined,
                provider_used=f"openrouter/{model_used}",
                user_id=user_id,
                reasoning=ai_data.get("reasoning", ""),
                routing_decision="pre_analyzed",
                analysis_status="pre_analyzed",
                url_scan_status=url_scan_status,
                urls_total=urls_total,
                urls_checked=urls_checked,
                received_at=received_at,
            )

            logger.info(
                f"[PREANALYZER Worker {worker_idx}] Done {email_id[:12]}: "
                f"score={score} label='{matched_label}' model={model_used}"
            )
            queue.task_done()

        except Exception as err:
            logger.warning(
                f"[PREANALYZER Worker {worker_idx}] Failed {email_id[:12]}: {err}. "
                f"Re-queueing to tail of the list..."
            )
            retries = email.get("_retries", 0)
            if retries < 3:
                email["_retries"] = retries + 1
                # Put back to the TAIL of the queue
                await queue.put(email)
            queue.task_done()
            # Brief backoff if key was rate limited or network hiccuped
            await asyncio.sleep(2.0)


async def run_background_preanalyzer(user_id: int) -> int:
    """
    Main entry point: Orchestrates the 20-worker dynamic pool.
    Pulls unpreanalyzed fetched emails, feeds them to the worker queue,
    and runs workers concurrently using dedicated OpenRouter keys.
    """
    keys = get_background_openrouter_keys()
    if not keys:
        logger.info("[PREANALYZER] No OPENROUTER_BACKGROUND_KEYS configured. Pre-analysis idle.")
        return 0

    safebrowsing_key = get_background_safebrowsing_key()

    # Avoid duplicate concurrent preanalyzer tasks for the same user
    async with _tasks_lock:
        existing_task = _active_user_tasks.get(user_id)
        if existing_task and not existing_task.done():
            logger.info(f"[PREANALYZER] Task already actively running for user {user_id}")
            return 0

    # Fetch user labels once
    available_labels_list = await asyncio.to_thread(get_labels, user_id)
    available_label_names = [lbl["label_name"] for lbl in available_labels_list]
    label_id_by_name = {lbl["label_name"].casefold(): lbl["label_id"] for lbl in available_labels_list}

    # Fetch unpreanalyzed emails from database (status='fetched', analysis_status!='pre_analyzed')
    unpreanalyzed = await asyncio.to_thread(get_unpreanalyzed_emails, user_id, limit=200)
    if not unpreanalyzed:
        logger.info(f"[PREANALYZER] No unpreanalyzed emails found for user {user_id}")
        return 0

    total_emails = len(unpreanalyzed)
    num_workers = min(len(keys), 20)
    logger.info(
        f"[PREANALYZER] Starting queue with {total_emails} emails using {num_workers} "
        f"concurrent workers (Keys loaded: {len(keys)})"
    )

    queue = asyncio.Queue()
    for email in unpreanalyzed:
        await queue.put(email)

    async def _orchestrator():
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=25),
            ) as client:
                worker_tasks = [
                    asyncio.create_task(
                        _worker_loop(
                            worker_idx=i + 1,
                            api_key=keys[i % len(keys)],
                            queue=queue,
                            user_id=user_id,
                            available_label_names=available_label_names,
                            label_id_by_name=label_id_by_name,
                            safebrowsing_key=safebrowsing_key,
                            client=client,
                        )
                    )
                    for i in range(num_workers)
                ]

                # Wait for queue to be fully processed
                await queue.join()

                # Cancel worker loops
                for t in worker_tasks:
                    t.cancel()
                await asyncio.gather(*worker_tasks, return_exceptions=True)

            logger.info(f"[PREANALYZER] Finished pre-analyzing batch for user {user_id}")
        finally:
            async with _tasks_lock:
                _active_user_tasks.pop(user_id, None)

    task = asyncio.create_task(_orchestrator())
    async with _tasks_lock:
        _active_user_tasks[user_id] = task

    return total_emails
