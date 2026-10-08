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
import json
import asyncio
import time
import httpx
from datetime import datetime
from pathlib import Path
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

# NVIDIA API (secondary fallback - fast model)
NVIDIA_API_KEY = _usable_secret(os.getenv("NVIDIA_API_KEY"))

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
        "llm7": {"configured": bool(LLM7_API_KEY)},
        "kilo": {"configured": True},
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


# ---------- AI CALL CONCURRENCY THROTTLE ----------

# Cap concurrent in-flight AI provider calls to avoid bursting past per-minute
# rate limits (Phase 13, Option 1). Increased to 10 for faster analysis.
AI_CALL_SEMAPHORE = asyncio.Semaphore(10)


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

You must respond with ONLY a valid JSON object. Do not include markdown, backticks, or any text outside the JSON object. The JSON must have exactly these four fields: label, scam_score, scam_indicators, reasoning.

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
    pass


class ProviderError(Exception):
    """Raised when an AI provider returns a non-recoverable error."""
    pass


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
        # httpx client with 30-second timeout for all requests
        self.client = httpx.Client(timeout=30.0)
        self.async_client = httpx.AsyncClient(timeout=30.0)
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
            f"gemini={bool(GEMINI_API_KEY)}, "
            f"cohere={bool(COHERE_API_KEY)}, "
            f"zai={bool(ZAI_API_KEY)}, "
            f"nvidia={bool(NVIDIA_API_KEY)}, "
            f"openrouter={bool(OPENROUTER_API_KEY)}, "
            f"llm7=keyless, kilo=keyless, ovh=keyless",
        )

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
        if not NVIDIA_API_KEY:
            raise ProviderError("NVIDIA API key not configured")

        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "meta/llama-3.1-8b-instruct",
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
            raise ProviderError("NVIDIA request timed out (30s)")

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
                error_msg = f"Groq key #{key_index + 1} timed out (30s)"
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
            raise QuotaError(f"All {len(GROQ_API_KEYS)} Groq API keys exhausted (quota)")
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
                    continue

                if response.status_code != 200:
                    raise ProviderError(f"Gemini error {response.status_code}: {response.text[:200]}")

                data = response.json()
                # Gemini response structure: candidates[0].content.parts[0].text
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

            except httpx.TimeoutException:
                raise ProviderError("Gemini request timed out (30s)")

        raise QuotaError(last_quota_error or "All Gemini API keys exhausted (quota)")

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
                raise QuotaError(f"Cohere quota exceeded: {response.text[:300]} | retry-after={retry_after}")

            if response.status_code != 200:
                raise ProviderError(f"Cohere error {response.status_code}: {response.text[:200]}")

            data = response.json()
            # v2 API response: message.content[0].text
            return data["message"]["content"][0]["text"].strip()

        except httpx.TimeoutException:
            raise ProviderError("Cohere request timed out (30s)")

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
                raise QuotaError(f"OpenRouter quota exceeded: {response.text[:300]} | retry-after={retry_after}")

            if response.status_code != 200:
                raise ProviderError(f"OpenRouter error {response.status_code}: {response.text[:200]}")

            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.TimeoutException:
            raise ProviderError("OpenRouter request timed out (30s)")
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
                raise QuotaError(f"Cloudflare quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"Cloudflare error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Cloudflare request timed out (30s)")

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
                raise QuotaError(f"Mistral quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"Mistral error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Mistral request timed out (30s)")

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
                raise QuotaError(f"Z AI quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"Z AI error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Z AI request timed out (30s)")

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
                raise QuotaError(f"LLM7 quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"LLM7 error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("LLM7 request timed out (30s)")

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
                raise QuotaError(f"Kilo Code quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"Kilo Code error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("Kilo Code request timed out (30s)")

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
                raise QuotaError(f"OVH quota exceeded: {response.text[:200]}")
            if response.status_code != 200:
                raise ProviderError(
                    f"OVH error {response.status_code}: {response.text[:200]}"
                )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            raise ProviderError("OVH request timed out (30s)")


    async def analyze(self, prompt: str) -> dict:
        """Run a prompt through the configured provider cascade."""
        providers = [
            ("Groq", self._call_groq),
            ("NVIDIA", self._call_nvidia),
            ("Gemini", self._call_gemini),
            ("Cohere", self._call_cohere),
            ("OpenRouter", self._call_openrouter),
            ("Cloudflare", self._call_cloudflare),
            ("Mistral", self._call_mistral),
            ("Z AI", self._call_zai),
            ("LLM7", self._call_llm7),
            ("Kilo", self._call_kilo),
            ("OVH", self._call_ovh),
        ]

        errors = []
        for name, call_fn in providers:
            try:
                logger.info(f"[AI] Trying {name}...")
                async with AI_CALL_SEMAPHORE:
                    response = await call_fn(prompt)
                logger.info(f"[AI] {name} responded successfully.")
                return {"response": response, "provider_used": name}
            except QuotaError as exc:
                errors.append(f"{name}: quota: {exc}")
                logger.info(f"[AI] {name} quota hit; switching provider.")
            except (ProviderError, Exception) as exc:
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                logger.info(f"[AI] {name} failed; switching provider: {exc}")

        return {
            "error": "All AI providers exhausted: " + " | ".join(errors),
            "provider_used": None,
        }

    async def analyze_json(self, prompt: str) -> dict:
        """Run the cascade and continue past providers with invalid JSON."""
        providers = [
            ("Groq", self._call_groq),
            ("NVIDIA", self._call_nvidia),
            ("Gemini", self._call_gemini),
            ("Cohere", self._call_cohere),
            ("OpenRouter", self._call_openrouter),
            ("Cloudflare", self._call_cloudflare),
            ("Mistral", self._call_mistral),
            ("Z AI", self._call_zai),
            ("LLM7", self._call_llm7),
            ("Kilo", self._call_kilo),
            ("OVH", self._call_ovh),
        ]
        errors = []
        for name, call_fn in providers:
            try:
                logger.info(f"[AI] Trying {name}...")
                async with AI_CALL_SEMAPHORE:
                    response = await call_fn(prompt)
                cleaned = response.strip().replace("```json", "").replace("```", "").strip()
                try:
                    data = json.loads(cleaned)
                except json.JSONDecodeError:
                    start = cleaned.find("{")
                    end = cleaned.rfind("}")
                    if start < 0 or end <= start:
                        raise ValueError("AI response was not valid JSON")
                    data = json.loads(cleaned[start:end + 1])
                logger.info(f"[AI] {name} responded successfully with valid JSON.")
                return {"data": data, "provider_used": name}
            except QuotaError as exc:
                errors.append(f"{name}: quota: {exc}")
                logger.info(f"[AI] {name} quota hit; switching provider.")
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                logger.info(f"[AI] {name} failed; switching provider: {exc}")
        return {"error": "All AI providers exhausted: " + " | ".join(errors), "provider_used": None}


ai_router = AIRouter()

