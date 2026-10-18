"""Regression tests for AI provider key loading without app/database imports."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def test_scalar_gemini_key_is_loaded_into_rotation_pool():
    """GEMINI_API_KEY must be usable even when no numbered key is set."""
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = "base-gemini-test-key"
    for index in range(1, 18):
        env.pop(f"GEMINI_API_KEY_{index}", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ai_router; print('base-gemini-test-key' in ai_router.GEMINI_API_KEYS)",
        ],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "True"


def test_placeholder_values_are_excluded_from_all_key_pools():
    env = os.environ.copy()
    for prefix, count in (("GROQ_API_KEY", 9), ("GEMINI_API_KEY", 17)):
        env[prefix] = "your_key_here"
        for index in range(1, count + 1):
            env[f"{prefix}_{index}"] = "your_key_here"
    env.update(
        {
            "GROQ_API_KEY": "your_key_here",
            "GROQ_API_KEY_1": "  ",
            "GROQ_API_KEY_2": "real-groq-test-key",
            "GEMINI_API_KEY": "<your-key>",
            "GEMINI_API_KEY_1": "redacted",
            "GEMINI_API_KEY_2": "real-gemini-test-key",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import ai_router; "
                "print(ai_router.GROQ_API_KEYS); "
                "print(ai_router.GEMINI_API_KEYS)"
            ),
        ],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = result.stdout.strip().splitlines()
    assert lines[-2:] == ["['real-groq-test-key']", "['real-gemini-test-key']"]


def test_numbered_provider_status_counts_scalar_and_numbered_keys():
    env = os.environ.copy()
    for prefix, count in (("GROQ_API_KEY", 9), ("GEMINI_API_KEY", 17)):
        env[prefix] = "your_key_here"
        for index in range(1, count + 1):
            env[f"{prefix}_{index}"] = "your_key_here"
    env.update(
        {
            "GROQ_API_KEY": "scalar-groq",
            "GROQ_API_KEY_1": "numbered-groq",
            "GROQ_API_KEY_2": "your_key_here",
            "GEMINI_API_KEY": "scalar-gemini",
            "GEMINI_API_KEY_1": "numbered-gemini",
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import ai_router; print(ai_router.get_provider_status())"
            ),
        ],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    status = ast.literal_eval(result.stdout.strip().splitlines()[-1])
    assert status["groq"] == {"configured": True, "key_count": 2}
    assert status["gemini"] == {"configured": True, "key_count": 2}
    assert status["cloudflare"] == {"configured": False}


def test_gemini_retries_remaining_keys_after_quota_response(monkeypatch):
    import asyncio
    import ai_router

    class Response:
        def __init__(self, status_code, text="", headers=None, payload=None):
            self.status_code = status_code
            self.text = text
            self.headers = headers or {}
            self._payload = payload or {}

        def json(self):
            return self._payload

    class Client:
        def __init__(self):
            self.keys = []

        async def post(self, url, *, json, headers, timeout):
            self.keys.append(headers["x-goog-api-key"])
            if len(self.keys) == 1:
                return Response(429, "quota")
            return Response(
                200,
                payload={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            )

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)
    router.async_client = Client()
    router._gemini_key_index = 0
    router._gemini_index_lock = asyncio.Lock()
    monkeypatch.setattr(ai_router, "GEMINI_API_KEYS", ["first", "second"])

    assert asyncio.run(router._call_gemini("prompt")) == "ok"
    assert router.async_client.keys == ["first", "second"]


def test_key_loading_is_independent_of_process_working_directory():
    env = os.environ.copy()
    env["GROQ_API_KEY"] = "cwd-independent-groq"
    env["GEMINI_API_KEY"] = "cwd-independent-gemini"
    env["PYTHONPATH"] = str(BACKEND)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ai_router; print(ai_router.GROQ_API_KEYS[0]); print(ai_router.GEMINI_API_KEYS[0])",
        ],
        cwd=BACKEND.parent,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-2:] == [
        "cwd-independent-groq",
        "cwd-independent-gemini",
    ]


def test_root_env_example_contains_placeholders_for_secret_fields():
    env_example = (BACKEND.parent / ".env.example").read_text()
    secret_names = (
        "GOOGLE_CLIENT_SECRET",
        "SESSION_SECRET_KEY",
        "JWT_SECRET_KEY",
        "DB_ENCRYPTION_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "COHERE_API_KEY",
        "NVIDIA_API_KEY",
        "OPENROUTER_API_KEY",
        "GOOGLE_SAFE_BROWSING_KEY",
    )
    for line in env_example.splitlines():
        if any(line.startswith(f"{name}=") for name in secret_names):
            assert line.endswith("=replace-with-local-secret")


def test_provider_cascade_reaches_last_resort_methods(monkeypatch):
    """Phase 2 Task 5: cascade follows the configured order and falls through.

    Only providers configured at startup are attempted (no retired NVIDIA, no
    keyless Kilo/LLM7 unless opted in); the last configured provider answers.
    """
    import asyncio
    import ai_router

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)
    attempted = []

    async def fail(name):
        attempted.append(name)
        raise ai_router.ProviderError(f"{name} unavailable")

    order = ["groq", "gemini", "cohere", "openrouter", "ovh"]
    for name in order[:-1]:
        monkeypatch.setattr(router, f"_call_{name}", lambda prompt, provider=name: fail(provider))
    monkeypatch.setattr(router, "_call_ovh", lambda prompt: asyncio.sleep(0, result="fallback"))

    router._configured = order
    router._provider_registry = {name: getattr(router, f"_call_{name}") for name in order}

    result = asyncio.run(router.analyze("prompt"))

    assert result == {"response": "fallback", "provider_used": "OVH"}
    assert attempted == ["groq", "gemini", "cohere", "openrouter"]


def test_provider_order_is_env_driven_and_skips_unconfigured(monkeypatch):
    """Phase 2 Task 5: AI_PROVIDER_ORDER sets order; unconfigured providers are dropped."""
    import ai_router

    monkeypatch.setattr(ai_router, "AI_PROVIDER_ORDER", ["ovh", "groq", "nvidia", "kilo"])
    monkeypatch.setattr(ai_router, "GROQ_API_KEYS", [])
    monkeypatch.setattr(ai_router, "NVIDIA_API_KEY", "set")
    monkeypatch.setattr(ai_router, "NVIDIA_MODEL", None)  # retired default stays disabled
    monkeypatch.setattr(ai_router, "ENABLE_KILO", False)

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)
    router._provider_registry = {"groq": None, "nvidia": None, "kilo": None, "ovh": None}

    assert router._resolve_configured_providers() == ["ovh"]


def test_match_label_handles_case_and_fuzzy_variants():
    """Phase 2 Task 9: case-insensitive and fuzzy label resolution."""
    from ai_router import match_label

    labels = ["Inbox", "Promotions", "Spam"]
    assert match_label("spam", labels) == "Spam"
    assert match_label("PROMOTIONS", labels) == "Promotions"
    assert match_label("Spam ", labels) == "Spam"
    assert match_label("banana", labels) is None
    assert match_label(None, labels) is None
    assert match_label("Spam", []) is None


def test_breaker_skips_provider_during_cooldown():
    """Phase 2 Task 7: a failed provider is skipped for the cooldown, then half-opens."""
    import asyncio
    import ai_router

    breaker = ai_router._ProviderBreaker()

    async def run():
        assert await breaker.is_available("Groq") is True
        await breaker.record_failure("Groq", retry_after=1)
        assert await breaker.is_available("Groq") is False
        assert "Groq" in breaker.snapshot()
        await asyncio.sleep(1.05)
        # Half-open: one probe admitted, a second concurrent probe is not.
        assert await breaker.is_available("Groq") is True
        assert await breaker.is_available("Groq") is False
        await breaker.record_success("Groq")
        assert await breaker.is_available("Groq") is True
        assert breaker.snapshot() == {}

    asyncio.run(run())


def test_analyze_uses_shared_breaker_across_calls():
    """Phase 2 Task 7: breaker state is process-wide, so a cooling provider is skipped later."""
    import asyncio
    import ai_router

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)
    calls = {"groq": 0}

    async def groq_fail(prompt):
        calls["groq"] += 1
        raise ai_router.QuotaError("rate limited", retry_after=60)

    async def ovh_ok(prompt):
        return "ok"

    router._configured = ["groq", "ovh"]
    router._provider_registry = {"groq": groq_fail, "ovh": ovh_ok}

    async def run():
        first = await router.analyze("p")
        second = await router.analyze("p")
        return first, second, calls["groq"]

    first, second, groq_calls = asyncio.run(run())
    assert first["provider_used"] == "OVH"
    assert second["provider_used"] == "OVH"
    assert groq_calls == 1  # second cascade skipped the open circuit


def test_label_only_returns_canonical_label(monkeypatch):
    """Phase 2 Task 9: the one-shot label call resolves to a real label."""
    import asyncio
    import ai_router

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)

    async def fake(prompt, parse_json=True):
        return {"data": {"label": "spam"}, "provider_used": "Groq"}

    monkeypatch.setattr(router, "_run_cascade", fake)

    assert asyncio.run(router.label_only("s@x.com", "subj", "body", ["Inbox", "Spam"])) == "Spam"
    assert asyncio.run(router.label_only("s@x.com", "subj", "body", [])) is None


def test_background_preanalyzer_key_loading_and_pause_and_failover(monkeypatch):
    """Test background preanalyzer key loading, pause/resume lock, and model failover."""
    import asyncio
    from background_preanalyzer import (
        get_background_openrouter_keys,
        get_background_safebrowsing_key,
        pause_preanalyzer,
        resume_preanalyzer,
        is_preanalyzer_paused,
        call_openrouter_with_failover,
        PRIMARY_MODEL,
        FALLBACK_MODEL,
    )

    # 1. Comma-separated Option B loading
    monkeypatch.setenv("OPENROUTER_BACKGROUND_KEYS", "key-1, key-2, key-3 ,, key-4")
    monkeypatch.setenv("BACKGROUND_SAFE_BROWSING_API_KEY", "bg-safebrowsing-key-123")
    keys = get_background_openrouter_keys()
    assert keys == ["key-1", "key-2", "key-3", "key-4"]
    assert get_background_safebrowsing_key() == "bg-safebrowsing-key-123"

    # 2. Pause / Resume control
    resume_preanalyzer()
    assert not is_preanalyzer_paused()
    pause_preanalyzer()
    assert is_preanalyzer_paused()
    resume_preanalyzer()
    assert not is_preanalyzer_paused()

    # 3. Model Failover: primary fails, fallback succeeds
    calls = []

    async def fake_call_openrouter(client, api_key, prompt, model):
        calls.append(model)
        if model == PRIMARY_MODEL:
            raise ValueError("Nemotron 503 Overloaded")
        return {
            "label": "Work",
            "scam_score": 5,
            "scam_indicators": [],
            "reasoning": "Legitimate work email",
        }

    monkeypatch.setattr("background_preanalyzer.call_openrouter_single", fake_call_openrouter)

    class DummyClient:
        pass

    async def run_failover():
        return await call_openrouter_with_failover(DummyClient(), "test-key", "test prompt")

    res, used_model = asyncio.run(run_failover())
    assert used_model == FALLBACK_MODEL
    assert res["label"] == "Work"
    assert res["scam_score"] == 5
    assert calls == [PRIMARY_MODEL, FALLBACK_MODEL]