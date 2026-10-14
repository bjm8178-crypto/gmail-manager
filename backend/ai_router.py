"""
ai_router.py — AI Cascade Router Module (Phase 3)
Routes AI analysis requests through multiple providers with automatic failover.
Cascade order: Groq (primary) → Gemini (secondary) → Cohere (tertiary)
NVIDIA is preserved as placeholder for future use.

Each provider has a 30-second timeout. If a provider returns 429 (quota exceeded),
the router automatically switches to the next provider in the cascade.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import os
import re
import json
import asyncio
import time
import difflib
import httpx
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable
from collections import deque
from dotenv import load_dotenv

# Load the backend-local environment first, then the repository-level fallback.
# This keeps imports independent of the process working directory.
_BACKEND_ROOT = Path(__file__).resolve().parent
load_dotenv(_BACKEND_ROOT / ".env", override=False)
load_dotenv(_BACKEND_ROOT.parent / ".env", override=False)


# ---------- API KEYS ----------

_PLACEHOLDER_VALUES = frozenset({
    "",
    "changeme",
    "change_me",
    "example",
    "example_key",
    "redacted",
    "your_key_here",
    "your-api-key",
    "your_api_key",
    "your-key",
    "your_key",
    "***",
})


def _usable_secret(value: str | None) -> str | None:
    """Return a normalized configured secret, excluding template values."""
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered in _PLACEHOLDER_VALUES:
        return None
    if lowered.startswith(("<your", "replace_me", "redacted:", "placeholder")):
        return None
    return candidate


def _load_key_pool(prefix: str, numbered_count: int) -> list[str]:
    """Load scalar and numbered keys in stable order without duplicates."""
    values = [os.getenv(prefix)]
    values.extend(os.getenv(f"{prefix}_{index}") for index in range(1, numbered_count + 1))
    keys = []
    for value in values:
        usable = _usable_secret(value)
        if usable and usable not in keys:
            keys.append(usable)
    return keys


# Groq API (primary) - scalar key followed by 9 rotating keys
GROQ_API_KEYS = _load_key_pool("GROQ_API_KEY", 9)
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else None

# NVIDIA API — disabled unless NVIDIA_MODEL is set (the previous default model is retired)
NVIDIA_API_KEY = _usable_secret(os.getenv("NVIDIA_API_KEY"))
NVIDIA_MODEL = _usable_secret(os.getenv("NVIDIA_MODEL"))

# Gemini API (secondary) - scalar key followed by 17 rotating keys
GEMINI_API_KEYS = _load_key_pool("GEMINI_API_KEY", 17)
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None


def get_provider_status() -> dict[str, dict[str, bool | int]]:
    """Return provider configuration using the same normalized credentials."""
    return {
        "groq": {"configured": bool(GROQ_API_KEYS), "key_count": len(GROQ_API_KEYS)},
        "nvidia": {"configured": bool(NVIDIA_API_KEY)},
        "gemini": {"configured": bool(GEMINI_API_KEYS), "key_count": len(GEMINI_API_KEYS)},
        "cohere": {"configured": bool(COHERE_API_KEY)},
        "openrouter": {"configured": bool(OPENROUTER_API_KEY)},
        "cloudflare": {"configured": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN)},
        "mistral": {"configured": bool(MISTRAL_API_KEY)},
        "zai": {"configured": bool(ZAI_API_KEY)},
        "llm7": {"configured": ENABLE_LLM7},
        "kilo": {"configured": ENABLE_KILO},
        "breaker_open": AI_BREAKER.snapshot(),
        "ovh": {"configured": True},
        "safebrowsing": {"configured": bool(GOOGLE_SAFE_BROWSING_KEY)},
    }

# Cohere API (tertiary)
COHERE_API_KEY = _usable_secret(os.getenv("COHERE_API_KEY"))

# OpenRouter API (quinary — free auto-router)
OPENROUTER_API_KEY = _usable_secret(os.getenv("OPENROUTER_API_KEY"))

# Cloudflare Workers AI (free: 10K neurons/day, Llama 3.3 70B FP8 Fast)
CLOUDFLARE_ACCOUNT_ID = _usable_secret(os.getenv("CLOUDFLARE_ACCOUNT_ID"))
CLOUDFLARE_API_TOKEN = _usable_secret(os.getenv("CLOUDFLARE_API_TOKEN"))

# Mistral AI (La Plateforme free tier: ~1 RPS, 500K TPM)
MISTRAL_API_KEY = _usable_secret(os.getenv("MISTRAL_API_KEY"))

# Z AI / Zhipu BigModel (GLM-4.5-Flash free)
ZAI_API_KEY = _usable_secret(os.getenv("ZAI_API_KEY") or os.getenv("ZHIPU_API_KEY"))

# LLM7.io (keyless by default; optional token for raised limits)
LLM7_API_KEY = _usable_secret(os.getenv("LLM7_API_KEY"))

# Kilo Code (no API key required; aggregator)
# OVHcloud AI Endpoints (keyless anonymous, 2 RPM/IP)
# Both are enabled unconditionally as last-resort fallbacks.

# Google Safe Browsing API
GOOGLE_SAFE_BROWSING_KEY = _usable_secret(os.getenv("GOOGLE_SAFE_BROWSING_KEY"))


# ---------- PHASE 2: CASCADE CONFIGURATION ----------

# Provider order is env-driven. Default: Groq -> Gemini -> Cohere -> OVH.
_DEFAULT_PROVIDER_ORDER = "groq,gemini,cohere,ovh"
AI_PROVIDER_ORDER = [
    name.strip().lower()
    for name in os.getenv("AI_PROVIDER_ORDER", _DEFAULT_PROVIDER_ORDER).split(",")
    if name.strip()
]

# Per-provider request timeout (seconds). Replaces the old 30-45s default.
AI_PROVIDER_TIMEOUT = float(os.getenv("AI_PROVIDER_TIMEOUT", "12"))

# Overall per-email AI deadline (seconds) across the entire cascade.
AI_DEADLINE = float(os.getenv("AI_DEADLINE", "30"))

# Circuit-breaker cooldown bounds (seconds).
AI_BREAKER_COOLDOWN = float(os.getenv("AI_BREAKER_COOLDOWN", "45"))
AI_BREAKER_MIN_COOLDOWN = float(os.getenv("AI_BREAKER_MIN_COOLDOWN", "30"))
AI_BREAKER_MAX_COOLDOWN = float(os.getenv("AI_BREAKER_MAX_COOLDOWN", "60"))

# Email-analysis concurrency (replaces the hard-coded Semaphore(2)).
ANALYZE_CONCURRENCY = max(1, int(os.getenv("ANALYZE_CONCURRENCY", "3")))

# Keyless providers are opt-in: Kilo returns 401 and LLM7 is off by default.
ENABLE_KILO = os.getenv("ENABLE_KILO", "false").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_LLM7 = os.getenv("ENABLE_LLM7", "false").strip().lower() in {"1", "true", "yes", "on"}


# ---------- AI CALL CONCURRENCY THROTTLE ----------

# Cap concurrent in-flight AI provider calls. Kept consistent with
# ANALYZE_CONCURRENCY so one analysis run cannot burst past its own bound.
AI_CALL_SEMAPHORE = asyncio.Semaphore(
    max(1, int(os.getenv("AI_CALL_CONCURRENCY", str(ANALYZE_CONCURRENCY))))
)


# ---------- COHERE PER-PROVIDER RATE LIMITER (Phase 16, Option B) ----------

class _FixedWindowRateLimiter:
    """
    Async-safe fixed-window rate limiter: at most `max_calls` grants per rolling
    `period` seconds. Excess callers wait (re-checking in <=0.5s slices) until a
    slot frees. A single acquire() waits at most `max_wait` seconds; if it still
    cannot get a slot it raises QuotaError so the normal cascade handler logs it
    and falls through. The internal lock is never held across a sleep (no
    deadlock, no over-grant).
    """

    def __init__(self, max_calls: int, period: float, max_wait: float):
        self.max_calls = max_calls
        self.period = period
        self.max_wait = max_wait
        self._grants = deque()          # monotonic timestamps of recent grants
        self._lock = asyncio.Lock()

    async def acquire(self, label: str = "Cohere") -> None:
        deadline = time.monotonic() + self.max_wait
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._grants and self._grants[0] <= now - self.period:
                    self._grants.popleft()
                if len(self._grants) < self.max_calls:
                    self._grants.append(now)
                    return
                wait = self._grants[0] + self.period - now
            # sleep OUTSIDE the lock so other tasks can proceed / free slots
            if time.monotonic() + min(wait, 0.5) > deadline:
                raise QuotaError(
                    f"{label} rate limiter: window full "
                    f"({self.max_calls}/{self.period:.0f}s), waited up to "
                    f"{self.max_wait:.0f}s | retry-after=None"
                )
            await asyncio.sleep(min(wait, 0.5))


# Cohere trial keys are hard-capped at 20 requests/minute. Enforce it locally so
# excess Cohere calls queue (<=30s) instead of 429-ing. Only applies to Cohere.
COHERE_RATE_LIMITER = _FixedWindowRateLimiter(max_calls=20, period=60.0, max_wait=30.0)


# ---------- PROMPT TEMPLATES ----------

CLASSIFICATION_PROMPT = """You are an email classification and scam detection AI. You will be given an email's sender, subject, body, URL security scan results, and a list of available classification labels.

Your job is to:
1. Classify the email into exactly ONE label from the provided available_labels list. You MUST copy the label name EXACTLY as it appears in the list, character-for-character, with exact capitalization and spacing. Do not paraphrase or use similar words.
2. Assign a scam probability score from 0 to 100 where 0 means definitely not a scam and 100 means definitely a scam.
3. List the specific phishing or scam indicators you detected. If none, return an empty list.
4. Provide a one-sentence reasoning for your classification.

IMPORTANT: The "label" field in your JSON response must be an EXACT MATCH (including capitalization) to one of the labels in the Available Labels list below. If none fit perfectly, choose the closest match from the list and copy its exact spelling.

Use these rules when deciding the scam_score:
- If url_threat_confirmed is true, a malicious URL was confirmed by Google Safe Browsing - the scam_score must be at least 70.
- If url_scan_unavailable is true, URL scanning failed (network error, timeout, etc.) - treat this as NEUTRAL information. Do not increase the score solely because scanning failed. Base your score on the email's content, sender, and other indicators.
- If the email contains urgency language such as "act now", "limited time", "your account will be suspended", "verify immediately", or similar phrases, add 20 to the base score.
- If the sender domain does not match the brand or company name mentioned in the subject or body, add 15 to the base score.
- If the email offers prizes, lottery winnings, inheritance, or unexpected money, add 25 to the base score.
- If the email asks for passwords, credit card numbers, OTP codes, or personal identification numbers, add 30 to the base score.
- Legitimate system-generated emails such as OTP codes, order confirmations, and bank transaction alerts from matching sender domains should receive a scam_score of 5 or below.

You must respond with ONLY a valid JSON object. Do not include markdown, backticks, or any text outside the JSON object. The JSON must have exactly these four fields: label (string, one value copied verbatim from the Available Labels list below), scam_score (integer 0-100), scam_indicators (array of strings), reasoning (string).
Any "label" value that is not byte-for-byte identical to one of the Available Labels is treated as invalid.

Input:
Sender: {sender}
Subject: {subject}
Body: {body}
URL Threat Confirmed (Google Safe Browsing): {url_threat_confirmed}
URL Scan Unavailable (network/API failure): {url_scan_unavailable}
Available Labels: {available_labels}

Remember: Copy one label from the Available Labels list EXACTLY as written above.
"""

REWRITE_PROMPT = """
Rewrite the following email text based on this instruction: {instruction}
Return ONLY the rewritten email text, no explanations, no preamble.

Original text:
{text}
"""


# ---------- CUSTOM EXCEPTIONS ----------

class QuotaError(Exception):
    """Raised when an AI provider returns 429 (quota/rate limit exceeded)."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderError(Exception):
    """Raised when an AI provider returns a non-recoverable error.

    `transient` marks failures (5xx, timeout, connection reset) that should
    open the shared circuit breaker; permanent errors (401/400) only skip the
    provider for the current cascade.
    """

    def __init__(self, message: str, transient: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.transient = transient
        self.retry_after = retry_after


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse a Retry-After header (seconds or HTTP-date) into float seconds."""
    try:
        raw = response.headers.get("Retry-After")
    except Exception:
        return None
    if not raw:
        return None
    raw = raw.strip()
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        pass
    try:
        when = parsedate_to_datetime(raw)
        delta = (when - datetime.now(when.tzinfo)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


# ---------- SHARED CIRCUIT BREAKER (Phase 2, Task 7) ----------

class _ProviderBreaker:
    """
    Process-wide circuit breaker shared by every email in the run.

    A provider that returns 429/5xx/timeout is skipped for a cooldown
    (Retry-After when supplied, otherwise AI_BREAKER_COOLDOWN), clamped to
    [AI_BREAKER_MIN_COOLDOWN, AI_BREAKER_MAX_COOLDOWN]. Once the cooldown
    elapses a single half-open probe is admitted; success closes the circuit,
    another failure re-opens it.
    """

    def __init__(self):
        self._open_until: dict[str, float] = {}
        self._probe_in_flight: set[str] = set()
        self._lock = asyncio.Lock()

    async def is_available(self, name: str) -> bool:
        async with self._lock:
            until = self._open_until.get(name)
            if until is None:
                return True
            if time.monotonic() < until:
                return False
            # Half-open: admit a single probe, block the rest.
            if name in self._probe_in_flight:
                return False
            self._probe_in_flight.add(name)
            return True

    async def record_success(self, name: str) -> None:
        async with self._lock:
            self._open_until.pop(name, None)
            self._probe_in_flight.discard(name)

    async def record_failure(self, name: str, retry_after: float | None = None) -> None:
        async with self._lock:
            self._probe_in_flight.discard(name)
            if retry_after is not None:
                # Task 6: honour the provider's Retry-After (small floor to avoid
                # thrash, capped so one provider cannot stall the run forever).
                cooldown = min(AI_BREAKER_MAX_COOLDOWN, max(1.0, retry_after))
            else:
                # Task 7: no hint -> default 30-60s window.
                cooldown = max(AI_BREAKER_MIN_COOLDOWN,
                               min(AI_BREAKER_MAX_COOLDOWN, AI_BREAKER_COOLDOWN))
            self._open_until[name] = time.monotonic() + cooldown
            logger.info(
                "[AI BREAKER] %s open for %.0fs (retry_after=%s)",
                name, cooldown, retry_after,
            )

    def snapshot(self) -> dict[str, float]:
        """Remaining cooldown seconds per open provider (0 entries omitted)."""
        now = time.monotonic()
        return {
            name: round(until - now, 1)
            for name, until in self._open_until.items()
            if until > now
        }


# One breaker for the whole process — every email shares it.
AI_BREAKER = _ProviderBreaker()


# ---------- LABEL MATCHING (Phase 2, Task 9) ----------

def match_label(label, available_labels: list[str], cutoff: float = 0.84) -> str | None:
    """
    Resolve an AI-returned label against the available labels.

    Exact match first, then case-insensitive match, then a conservative fuzzy
    match on normalized text. Returns the canonical label name, or None.
    """
    if not isinstance(label, str) or not available_labels:
        return None
    candidate = label.strip()
    if not candidate:
        return None

    for name in available_labels:
        if name == candidate:
            return name
    folded = candidate.casefold()
    for name in available_labels:
        if name.casefold() == folded:
            return name

    def _normalize(value: str) -> str:
        return "".join(ch for ch in value.casefold() if ch.isalnum())

    normalized = _normalize(candidate)
    if not normalized:
        return None
    for name in available_labels:
        if _normalize(name) == normalized:
            return name
    close = difflib.get_close_matches(
        candidate.casefold(), [n.casefold() for n in available_labels], n=1, cutoff=cutoff
    )
    if close:
        target = close[0]
        for name in available_labels:
            if name.casefold() == target:
                return name
    return None


LABEL_ONLY_PROMPT = """You are labeling an email. Respond with ONLY a JSON object of the form {{"label": "<one label>"}}.

Available Labels: {available_labels}

Email:
Sender: {sender}
Subject: {subject}
Body: {body}
"""


# ---------- AI ROUTER CLASS ----------

class AIRouter:
    """
    Routes AI requests through a cascade of providers.
    If the primary provider is rate-limited (429), automatically falls back
    to the next provider in the chain.
    
    Cascade order: Groq → NVIDIA → Gemini → Cohere → OpenRouter
    (NVIDIA preserved but not in active cascade)
    """

    def __init__(self):
        # Phase 2 Task 6: per-provider timeout (was 30s) + overall AI deadline.
        self.client = httpx.Client(timeout=AI_PROVIDER_TIMEOUT)
        self.async_client = httpx.AsyncClient(timeout=AI_PROVIDER_TIMEOUT)
        self._gemini_key_index = 0
        self._gemini_index_lock = asyncio.Lock()  # Protects Gemini key rotation
        self._groq_key_index = 0
        self._groq_index_lock = asyncio.Lock()  # Protects Groq key rotation
        # OpenRouter does not need key rotation (single key)
        logger.info(
            f"[AI ROUTER] Providers loaded: "
            f"groq={len(GROQ_API_KEYS)} keys, "
            f"cloudflare={bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN)}, "
            f"mistral={bool(MISTRAL_API_KEY)}, "
            f"gemini={bool(GEMINI_API_KEYS)}, "
            f"cohere={bool(COHERE_API_KEY)}, "
            f"zai={bool(ZAI_API_KEY)}, "
            f"nvidia={bool(NVIDIA_API_KEY and NVIDIA_MODEL)}, "
            f"openrouter={bool(OPENROUTER_API_KEY)}, "
            f"llm7={'enabled' if ENABLE_LLM7 else 'disabled'}, "
            f"kilo={'enabled' if ENABLE_KILO else 'disabled'}, "
            f"ovh=keyless"
        )
        # Phase 2 Task 5: only providers configured at startup enter the cascade.
        self._provider_registry: dict[str, Callable[[str], "asyncio.Future[str]"] ] = {
            "groq": self._call_groq,
            "gemini": self._call_gemini,
            "cohere": self._call_cohere,
            "ovh": self._call_ovh,
            "openrouter": self._call_openrouter,
            "cloudflare": self._call_cloudflare,
            "mistral": self._call_mistral,
            "zai": self._call_zai,
            "nvidia": self._call_nvidia,
            "llm7": self._call_llm7,
            "kilo": self._call_kilo,
        }
        self._configured = self._resolve_configured_providers()
        logger.info(f"[AI ROUTER] Cascade order: {' -> '.join(self._configured) or 'none'}")

    def _resolve_configured_providers(self) -> list[str]:
            """Return the env-ordered subset of providers actually configured."""
            availability = {
                "groq": bool(GROQ_API_KEYS),
                "gemini": bool(GEMINI_API_KEYS),
                "cohere": bool(COHERE_API_KEY),
                "ovh": True,
                "openrouter": bool(OPENROUTER_API_KEY),
                "cloudflare": bool(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN),
                "mistral": bool(MISTRAL_API_KEY),
                "zai": bool(ZAI_API_KEY),
                # NVIDIA's default model is retired; require an explicit model to enable it.
                "nvidia": bool(NVIDIA_API_KEY and NVIDIA_MODEL),
                # Kilo 401s without a key and LLM7 is off by default — opt-in only.
                "kilo": ENABLE_KILO,
                "llm7": ENABLE_LLM7,
            }
            ordered = [name for name in AI_PROVIDER_ORDER if name in availability]
            selected = [name for name in ordered if availability[name]]
            unknown = [name for name in ordered if name not in self._provider_registry]
            if unknown:
                logger.warning(f"[AI ROUTER] Unknown providers in AI_PROVIDER_ORDER: {unknown}")
            return selected

    # ---------- PROVIDER: NVIDIA (PLACEHOLDER — NOT IN ACTIVE CASCADE) ----------

    async def _call_nvidia(self, prompt: str) -> str:
        """
        Call NVIDIA API (OpenAI-compatible endpoint).
        Call NVIDIA API with nemotron-3-nano-30b-a3b (fast model).
        
        Args:
            prompt: The text prompt to send
            
        Returns:
            Response text from the model
            
        Raises:
            QuotaError: If status 429 (rate limited)
            ProviderError: If any other error occurs
        """
        if not (NVIDIA_API_KEY and NVIDIA_MODEL):
            raise ProviderError("NVIDIA not configured (set NVIDIA_API_KEY and NVIDIA_MODEL)")

        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": NVIDIA_MODEL,
            "messages": [{
                "role": "system",
                "content": (
                    "Respond with ONLY one valid JSON object. Do not explain your reasoning, "
                    "think out loud, use markdown, or output code fences."
                ),
            }, {
                "role": "user",
                "content": prompt,
            }],
            "max_tokens": 8192,  # FIX #5 - Raised from 500 to prevent truncation
            "temperature": 0.2,
            "stream": False,
        }

        try:
            response = await self.async_client.post(url, headers=headers, json=body)

            if response.status_code == 429:
                raise QuotaError("NVIDIA quota exceeded")

            if response.status_code != 200:
                raise ProviderError(f"NVIDIA error {response.status_code}: {response.text[:200]}")

            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
            logger.info(f"[AI NVIDIA RAW] {raw_content!r}")
            return raw_content.strip()

        except httpx.TimeoutException:
            raise ProviderError("NVIDIA request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    # ---------- PROVIDER: GROQ (PRIMARY) ----------

    async def _call_groq(self, prompt: str) -> str:
        """
        Call Groq API with llama-3.1-8b-instant model, rotating through 9 API keys.
        Primary AI provider. Called first in the cascade.
        
        Tries all available Groq API keys in round-robin order before raising QuotaError.
        If one key hits 429 (quota), immediately tries the next key. Only fails when
        ALL keys are exhausted.
        
        Args:
            prompt: The text prompt to send
            
        Returns:
            Response text from the model
            
        Raises:
            QuotaError: If ALL keys return 429
            ProviderError: If ALL keys fail with non-quota errors
        """
        if not GROQ_API_KEYS:
            raise ProviderError("Groq API keys not configured")

        url = "https://api.groq.com/openai/v1/chat/completions"
        body = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,  # FIX #5 - Raised from 1200 to prevent truncation
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "low",
        }

        quota_errors = 0
        other_errors = []
        last_retry_after = None
        
        # Try all keys in rotation before giving up
        # Lock ensures atomicity of read-modify-write on key index
        for attempt in range(len(GROQ_API_KEYS)):
            async with self._groq_index_lock:
                key_index = (self._groq_key_index + attempt) % len(GROQ_API_KEYS)
            api_key = GROQ_API_KEYS[key_index]
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            try:
                response = await self.async_client.post(url, headers=headers, json=body)

                if response.status_code == 429:
                    quota_errors += 1
                    retry_after = response.headers.get("Retry-After")
                    last_retry_after = _parse_retry_after(response)
                    logger.info(f"[AI] Groq key #{key_index + 1} quota hit, trying next key...")
                    continue  # Try next key immediately

                if response.status_code != 200:
                    error_msg = f"Groq key #{key_index + 1} error {response.status_code}: {response.text[:200]}"
                    other_errors.append(error_msg)
                    logger.info(f"[AI] {error_msg}, trying next key...")
                    continue  # Try next key

                # Success - update index for next call and return
                async with self._groq_index_lock:
                    self._groq_key_index = (key_index + 1) % len(GROQ_API_KEYS)
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()

            except httpx.TimeoutException:
                error_msg = f"Groq key #{key_index + 1} timed out ({AI_PROVIDER_TIMEOUT:.0f}s)"
                other_errors.append(error_msg)
                logger.info(f"[AI] {error_msg}, trying next key...")
                continue  # Try next key
            except Exception as e:
                error_msg = f"Groq key #{key_index + 1} exception: {e}"
                other_errors.append(error_msg)
                logger.info(f"[AI] {error_msg}, trying next key...")
                continue  # Try next key

        # All keys exhausted - raise appropriate error
        if quota_errors == len(GROQ_API_KEYS):
            raise QuotaError(
                f"All {len(GROQ_API_KEYS)} Groq API keys exhausted (quota)", last_retry_after
            )
        else:
            raise ProviderError(f"All {len(GROQ_API_KEYS)} Groq keys failed: {' | '.join(other_errors)}")

    # ---------- PROVIDER: GEMINI (SECONDARY) ----------

    async def _call_gemini(self, prompt: str) -> str:
        """
        Call Google Gemini Flash API.
        
        Args:
            prompt: The text prompt to send
            
        Returns:
            Response text from the model
            
        Raises:
            QuotaError: If status 429
            ProviderError: If any other error
        """
        if not GEMINI_API_KEYS:
            raise ProviderError("Gemini API key not configured")

        async with self._gemini_index_lock:
            start_index = self._gemini_key_index % len(GEMINI_API_KEYS)
            self._gemini_key_index += 1

        last_quota_error = None
        last_retry_after = None
        for offset in range(len(GEMINI_API_KEYS)):
            key = GEMINI_API_KEYS[(start_index + offset) % len(GEMINI_API_KEYS)]

            # SEC-004 fix: API key in header, not URL query string
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            }
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 8192,  # FIX #5 - Raised from 1200 to prevent truncation
                    "thinkingConfig": {"thinkingBudget": 0},
                    "responseMimeType": "application/json",
                }
            }

            try:
                response = await self.async_client.post(url, json=body, headers=headers, timeout=30.0)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is None:
                        # Gemini puts the delay in the body: error.details[].RetryInfo.retryDelay ("10s")
                        try:
                            for d in response.json().get("error", {}).get("details", []):
                                if str(d.get("@type", "")).endswith("RetryInfo") and d.get("retryDelay"):
                                    retry_after = str(d["retryDelay"]).rstrip("s")
                                    break
                        except Exception:
                            pass
                    last_quota_error = (
                        f"Gemini quota exceeded: {response.text[:300]} | "
                        f"retry-after={retry_after}"
                    )
                    last_retry_after = _parse_retry_after(response)
                    continue

                if response.status_code != 200:
                    raise ProviderError(
                        f"Gemini error {response.status_code}: {response.text[:200]}",
                        transient=response.status_code >= 500 or response.status_code == 408,
                        retry_after=_parse_retry_after(response),
                    )

                data = response.json()
                # Gemini response structure: candidates[0].content.parts[0].text
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            except httpx.TimeoutException:
                raise ProviderError(
                    f"Gemini request timed out ({AI_PROVIDER_TIMEOUT:.0f}s)", transient=True
                )

        raise QuotaError(last_quota_error or "All Gemini API keys exhausted (quota)", last_retry_after)

    # ---------- PROVIDER: COHERE (TERTIARY) ----------

    async def _call_cohere(self, prompt: str) -> str:
        """
        Call Cohere API with command-a-03-2025 model (latest available).
        Uses v2 chat endpoint.
        
        Args:
            prompt: The text prompt to send
            
        Returns:
            Response text from the model
            
        Raises:
            QuotaError: If status 429
            ProviderError: If any other error
        """
        if not COHERE_API_KEY:
            raise ProviderError("Cohere API key not configured")

        url = "https://api.cohere.com/v2/chat"
        headers = {
            "Authorization": f"Bearer {COHERE_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "command-a-03-2025",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,  # FIX #5 - Raised from 500 to prevent truncation
            "temperature": 0.2,
        }

        try:
            response = await self.async_client.post(url, headers=headers, json=body)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise QuotaError(f"Cohere quota exceeded: {response.text[:300]} | retry-after={retry_after}", _parse_retry_after(response))

            if response.status_code != 200:
                raise ProviderError(
                    f"Cohere error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )

            data = response.json()
            # v2 API response: message.content[0].text
            return data["message"]["content"][0]["text"].strip()

        except httpx.TimeoutException:
            raise ProviderError("Cohere request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    # ---------- PROVIDER: OPENROUTER (QUINARY) ----------

    async def _call_openrouter(self, prompt: str) -> str:
        """
        Call OpenRouter API with a verified free instruction model.
        Uses openai/gpt-oss-20b:free.
        
        Args:
            prompt: The text prompt to send
            
        Returns:
            Response text from the model
            
        Raises:
            QuotaError: If status 429 (rate limited)
            ProviderError: If any other error occurs
        """
        if not OPENROUTER_API_KEY:
            raise ProviderError("OpenRouter API key not configured")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://gmail-manager.app",
            "X-Title": "Gmail Manager",
        }
        body = {
            "model": "openai/gpt-oss-20b:free",
            "messages": [{
                "role": "system",
                "content": (
                    "Respond with ONLY one valid JSON object. Do not explain your reasoning, "
                    "think out loud, use markdown, or output code fences."
                ),
            }, {
                "role": "user",
                "content": prompt,
            }],
            "max_tokens": 8192,  # FIX #5 - Raised from 1200 to prevent truncation
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self.async_client.post(url, headers=headers, json=body)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise QuotaError(f"OpenRouter quota exceeded: {response.text[:300]} | retry-after={retry_after}", _parse_retry_after(response))

            if response.status_code != 200:
                raise ProviderError(
                    f"OpenRouter error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )

            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.TimeoutException:
            raise ProviderError("OpenRouter request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)
        except KeyError as e:
            raise ProviderError(f"OpenRouter unexpected response format: missing {e}")

    # ---------- PROVIDER: CLOUDFLARE WORKERS AI ----------

    async def _call_cloudflare(self, prompt: str) -> str:
        """Call Cloudflare Workers AI (OpenAI-compatible) with Llama 3.3 70B FP8 Fast."""
        if not (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN):
            raise ProviderError("Cloudflare account id / token not configured")

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions"
        )
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            "messages": [{
                "role": "system",
                "content": (
                    "Respond with ONLY one valid JSON object. No markdown, no commentary."
                ),
            }, {"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"Cloudflare quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"Cloudflare error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Cloudflare request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    # ---------- PROVIDER: MISTRAL AI ----------

    async def _call_mistral(self, prompt: str) -> str:
        """Call Mistral AI La Plateforme with mistral-large-latest."""
        if not MISTRAL_API_KEY:
            raise ProviderError("Mistral API key not configured")

        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"Mistral quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"Mistral error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Mistral request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    # ---------- PROVIDER: Z AI (ZHIPU BIGMODEL) ----------

    async def _call_zai(self, prompt: str) -> str:
        """Call Zhipu AI BigModel with GLM-4.5-Flash (free, OpenAI-compatible)."""
        if not ZAI_API_KEY:
            raise ProviderError("Z AI (Zhipu) API key not configured")

        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {
            "Authorization": f"Bearer {ZAI_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "glm-4.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"Z AI quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"Z AI error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Z AI request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    # ---------- KEYLESS FALLBACKS ----------

    async def _call_llm7(self, prompt: str) -> str:
        """Call LLM7.io (keyless, DeepSeek-V4-Flash). Token optional for raised limits."""
        url = "https://api.llm7.io/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if LLM7_API_KEY:
            headers["Authorization"] = f"Bearer {LLM7_API_KEY}"
        body = {
            "model": "DeepSeek-V4-Flash-0731",
            "messages": [{
                "role": "system",
                "content": (
                    "Respond with ONLY one valid JSON object. No markdown fences, no commentary, "
                    "no reasoning out loud."
                ),
            }, {"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"LLM7 quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"LLM7 error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("LLM7 request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    async def _call_kilo(self, prompt: str) -> str:
        """Call Kilo Code gateway (keyless, routes to a free pooled model)."""
        url = "https://api.kilo.ai/api/gateway/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        body = {
            "model": "kilo-auto/efficient",
            "messages": [{
                "role": "system",
                "content": "Respond with ONLY one valid JSON object. No markdown, no commentary.",
            }, {"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"Kilo Code quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"Kilo Code error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Kilo Code request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)

    async def _call_ovh(self, prompt: str) -> str:
        """Call OVHcloud AI Endpoints (keyless, Llama 3.3 70B, hard 2 RPM/IP)."""
        url = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        body = {
            "model": "Meta-Llama-3_3-70B-Instruct",
            "messages": [{
                "role": "system",
                "content": "Respond with ONLY one valid JSON object. No markdown, no commentary.",
            }, {"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.2,
        }
        try:
            response = await self.async_client.post(url, headers=headers, json=body)
            if response.status_code == 429:
                raise QuotaError(f"OVH quota exceeded: {response.text[:200]}", _parse_retry_after(response))
            if response.status_code != 200:
                raise ProviderError(
                    f"OVH error {response.status_code}: {response.text[:200]}",
                    transient=response.status_code >= 500, retry_after=_parse_retry_after(response),
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("OVH request timed out ({0:.0f}s)".format(AI_PROVIDER_TIMEOUT), transient=True)


    # ---------- CASCADE HELPERS (Phase 2) ----------

    def _cascade_providers(self):
        """Return (display_name, call_fn) pairs in configured order."""
        display = {
            "groq": "Groq", "gemini": "Gemini", "cohere": "Cohere", "ovh": "OVH",
            "openrouter": "OpenRouter", "cloudflare": "Cloudflare",
            "mistral": "Mistral", "zai": "Z AI", "nvidia": "NVIDIA",
            "llm7": "LLM7", "kilo": "Kilo",
        }
        return [(display[name], self._provider_registry[name]) for name in self._configured]

    async def _call_with_timeout(self, name, call_fn, prompt):
        """Invoke one provider bounded by the per-provider timeout."""
        try:
            return await asyncio.wait_for(call_fn(prompt), timeout=AI_PROVIDER_TIMEOUT)
        except asyncio.TimeoutError:
            raise ProviderError(
                "{0} timed out ({1:.0f}s)".format(name, AI_PROVIDER_TIMEOUT), transient=True
            )

    async def _run_cascade(self, prompt, parse_json):
        """
        Shared cascade loop for both analyze() and analyze_json().

        Phase 2 Task 5: only startup-configured providers are attempted.
        Phase 2 Task 6: overall per-email AI deadline + Retry-After honoured.
        Phase 2 Task 7: shared circuit breaker skips cooling-down providers.
        """
        deadline = time.monotonic() + AI_DEADLINE
        errors = []
        providers = self._cascade_providers()
        if not providers:
            return {"error": "No AI providers configured", "provider_used": None}

        for name, call_fn in providers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                errors.append("cascade deadline exceeded ({0:.0f}s)".format(AI_DEADLINE))
                logger.info("[AI] Overall AI deadline exceeded; stopping cascade.")
                break

            if not await AI_BREAKER.is_available(name):
                errors.append(name + ": circuit open")
                logger.info("[AI] {0} skipped (circuit open).".format(name))
                continue

            try:
                logger.info("[AI] Trying {0}...".format(name))
                async with AI_CALL_SEMAPHORE:
                    response = await asyncio.wait_for(
                        self._call_with_timeout(name, call_fn, prompt),
                        timeout=remaining,
                    )
                if parse_json:
                    data = self._parse_json_response(response)
                    await AI_BREAKER.record_success(name)
                    logger.info("[AI] {0} responded successfully with valid JSON.".format(name))
                    return {"data": data, "provider_used": name}
                await AI_BREAKER.record_success(name)
                logger.info("[AI] {0} responded successfully.".format(name))
                return {"response": response, "provider_used": name}

            except QuotaError as exc:
                errors.append("{0}: quota: {1}".format(name, exc))
                logger.info("[AI] {0} quota hit; switching provider.".format(name))
                await AI_BREAKER.record_failure(name, getattr(exc, "retry_after", None))
            except asyncio.TimeoutError:
                errors.append(name + ": timeout")
                logger.info("[AI] {0} exceeded remaining deadline; switching provider.".format(name))
                await AI_BREAKER.record_failure(name)
            except ProviderError as exc:
                errors.append("{0}: {1}: {2}".format(name, type(exc).__name__, exc))
                logger.info("[AI] {0} failed; switching provider: {1}".format(name, exc))
                if exc.transient:
                    await AI_BREAKER.record_failure(name, exc.retry_after)
            except ValueError as exc:
                # Invalid JSON from an otherwise healthy provider: skip, keep available.
                errors.append("{0}: invalid JSON: {1}".format(name, exc))
                logger.info("[AI] {0} returned invalid JSON; switching provider.".format(name))
            except Exception as exc:
                errors.append("{0}: {1}: {2}".format(name, type(exc).__name__, exc))
                logger.info("[AI] {0} failed; switching provider: {1}".format(name, exc))

        return {"error": "All AI providers exhausted: " + " | ".join(errors), "provider_used": None}

    @staticmethod
    def _parse_json_response(response):
        """Parse a provider response into JSON, tolerating fences and prose."""
        cleaned = response.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            jstart = cleaned.find("{")
            jend = cleaned.rfind("}")
            if jstart < 0 or jend <= jstart:
                raise ValueError("AI response was not valid JSON")
            return json.loads(cleaned[jstart:jend + 1])

    async def analyze(self, prompt):
        """Run a prompt through the configured provider cascade."""
        return await self._run_cascade(prompt, parse_json=False)

    async def analyze_json(self, prompt):
        """Run the cascade and continue past providers with invalid JSON."""
        return await self._run_cascade(prompt, parse_json=True)

    async def label_only(self, sender, subject, body, available_labels):
        """
        Phase 2 Task 9: one tiny follow-up call asking only for the label.

        Used when a response carried a valid scam_score but an unusable label.
        Returns the canonical label name, or None if it cannot be resolved.
        """
        if not available_labels:
            return None
        prompt = LABEL_ONLY_PROMPT.format(
            available_labels=", ".join(available_labels),
            sender=sender, subject=subject, body=(body or "")[:1500],
        )
        result = await self._run_cascade(prompt, parse_json=True)
        data = result.get("data")
        if not isinstance(data, dict):
            return None
        return match_label(data.get("label"), available_labels)



ai_router = AIRouter()
