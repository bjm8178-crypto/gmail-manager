"""Regression tests for AI provider key loading without app/database imports."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).parent


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
    import asyncio
    import ai_router

    router = ai_router.AIRouter.__new__(ai_router.AIRouter)
    attempted = []

    async def fail(name):
        attempted.append(name)
        raise ai_router.ProviderError(f"{name} unavailable")

    for name in ("groq", "nvidia", "gemini", "cohere", "openrouter", "cloudflare", "mistral", "zai", "llm7", "kilo"):
        monkeypatch.setattr(router, f"_call_{name}", lambda prompt, provider=name: fail(provider))
    monkeypatch.setattr(router, "_call_ovh", lambda prompt: asyncio.sleep(0, result="fallback"))

    result = asyncio.run(router.analyze("prompt"))

    assert result == {"response": "fallback", "provider_used": "OVH"}
    assert attempted == ["groq", "nvidia", "gemini", "cohere", "openrouter", "cloudflare", "mistral", "zai", "llm7", "kilo"]