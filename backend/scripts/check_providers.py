#!/usr/bin/env python3
"""
Provider connectivity check script.
Task 7: Test each configured provider with one minimal request.
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path and load .env before importing ai_router
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from dotenv import load_dotenv
load_dotenv(_BACKEND_ROOT / ".env", override=False)

# Now import ai_router (which will see the loaded environment)
from ai_router import AIRouter, QuotaError, ProviderError


async def check_provider(router: AIRouter, name: str, call_fn) -> tuple[str, str, str]:
    """
    Test one provider with minimal prompt.
    
    Returns:
        (provider_name, "PASS"|"FAIL", error_description)
    """
    try:
        # Use asyncio.wait_for for 10-second timeout per provider
        response = await asyncio.wait_for(
            call_fn("Reply with the word OK"),
            timeout=10.0
        )
        # Success if we got any non-empty response
        if response and response.strip():
            return (name, "PASS", "")
        else:
            return (name, "FAIL", "ProviderError: empty response")
    except asyncio.TimeoutError:
        return (name, "FAIL", "TimeoutError: exceeded 10s")
    except QuotaError as e:
        # QuotaError is a specific failure mode, not a configuration issue
        return (name, "FAIL", f"QuotaError: {str(e)[:60]}")
    except ProviderError as e:
        return (name, "FAIL", f"ProviderError: {str(e)[:60]}")
    except Exception as e:
        exc_class = e.__class__.__name__
        exc_msg = str(e)[:60]
        return (name, "FAIL", f"{exc_class}: {exc_msg}")


async def main():
    router = AIRouter()
    
    # List of (name, call_fn) matching ai_router.py's provider methods
    providers = [
        ("Groq", router._call_groq),
        ("NVIDIA", router._call_nvidia),
        ("Gemini", router._call_gemini),
        ("Cohere", router._call_cohere),
        ("OpenRouter", router._call_openrouter),
        ("Cloudflare", router._call_cloudflare),
        ("Mistral", router._call_mistral),
        ("Z AI", router._call_zai),
        ("LLM7", router._call_llm7),
        ("Kilo", router._call_kilo),
        ("OVH", router._call_ovh),
    ]
    
    # Check each provider sequentially
    for name, call_fn in providers:
        provider_name, status, error_desc = await check_provider(router, name, call_fn)
        if status == "PASS":
            print(f"{provider_name}: PASS")
        else:
            print(f"{provider_name}: FAIL — {error_desc}")
    
    # Close async client
    await router.async_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
