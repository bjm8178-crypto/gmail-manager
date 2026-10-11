"""
test_rate_limiting.py — Tests for SlowAPI rate limiting middleware.

Tests verify that rate limits are properly enforced on critical endpoints.
Phase 1: Rate Limiting Implementation (Feature Gaps Sprint).

Note: These are integration tests that verify rate limit decorators are applied.
Full rate limit testing requires running server and making actual HTTP requests.
"""

import pytest


def test_rate_limit_imports():
    """Verify SlowAPI dependencies are available."""
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        assert True, "SlowAPI imports successful"
    except ImportError as e:
        pytest.fail(f"SlowAPI import failed: {e}")


def test_rate_limit_configuration():
    """Verify rate limiter is configured in main.py."""
    import main
    
    # Check limiter exists
    assert hasattr(main, 'limiter'), "Limiter not found in main module"
    assert main.limiter is not None, "Limiter is None"
    
    # Check app has limiter state
    assert hasattr(main.app.state, 'limiter'), "Limiter not attached to app.state"


def test_rate_limited_endpoints_decorated():
    """
    Verify critical endpoints have @limiter.limit() decorators.
    This test checks source code for rate limit decorators.
    """
    import inspect
    import main
    
    # List of endpoints that should be rate-limited
    rate_limited_functions = [
        'auth_login',           # 5/minute
        'auth_callback',        # 10/minute
        'emails_analyze_bulk',  # 3/hour
        'retry_failed_emails',  # 5/hour
        'emails_batch_delete',  # 5/hour
        'batch_label_update',   # 10/hour
        'ai_rewrite',          # 10/minute
        'patch_mark_email_safe',  # 30/minute
        'update_email_label',     # 30/minute
        'quarantine_delete',      # 30/minute
        'quarantine_mark_safe',   # 30/minute
    ]
    
    missing_rate_limits = []
    
    for func_name in rate_limited_functions:
        if hasattr(main, func_name):
            func = getattr(main, func_name)
            source = inspect.getsource(func)
            
            # Check if @limiter.limit() appears before the function definition
            if '@limiter.limit' not in source:
                missing_rate_limits.append(func_name)
        else:
            missing_rate_limits.append(f"{func_name} (not found)")
    
    assert len(missing_rate_limits) == 0, \
        f"Functions missing rate limits: {missing_rate_limits}"


def test_rate_limit_coverage_documentation():
    """
    Document which endpoints have rate limits applied.
    This serves as living documentation of our rate limit strategy.
    """
    expected_rate_limits = {
        # Auth endpoints (per-IP) — prevent credential stuffing
        "GET /auth/login": "5/minute",
        "GET /auth/callback": "10/minute",
        
        # Bulk operations (per-user) — prevent resource exhaustion
        "POST /emails/analyze-bulk": "3/hour",
        "POST /emails/retry-failed": "5/hour",
        "POST /emails/batch-delete": "5/hour",
        "POST /emails/batch-label": "10/hour",
        
        # AI endpoints (per-user) — prevent API quota exhaustion
        "POST /ai/rewrite": "10/minute",
        
        # Email mutations (per-user) — reasonable UX limits
        "PATCH /emails/{id}/mark-safe": "30/minute",
        "PUT /emails/{id}/label": "30/minute",
        "DELETE /quarantine/{id}": "30/minute",
        "POST /quarantine/{id}/safe": "30/minute",
    }
    
    # Verify we have 11 protected endpoints as planned
    assert len(expected_rate_limits) == 11, \
        f"Expected 11 rate-limited endpoints, documented {len(expected_rate_limits)}"
    
    print("\n✅ Rate Limit Coverage:")
    for endpoint, limit in expected_rate_limits.items():
        print(f"  {endpoint:40s} → {limit}")


def test_rate_limit_strategy():
    """
    Document the rate limiting strategy for future reference.
    This test always passes but serves as living documentation.
    """
    strategy = {
        "Auth endpoints": {
            "scope": "per-IP (anonymous)",
            "reason": "Prevent credential stuffing, brute force attacks",
            "limits": "5-10/minute — low enough to block bots, high enough for legitimate users"
        },
        "Bulk operations": {
            "scope": "per-user (authenticated)",
            "reason": "Prevent resource exhaustion, AI quota depletion, accidental runaway jobs",
            "limits": "3-10/hour — expensive operations that should be infrequent"
        },
        "AI endpoints": {
            "scope": "per-user",
            "reason": "Protect OpenAI API quota, prevent cost overruns",
            "limits": "10/minute — reasonable for rewriting 1-2 emails"
        },
        "Email mutations": {
            "scope": "per-user",
            "reason": "Prevent accidental mass-operations (e.g., clicking 'delete' 100 times)",
            "limits": "30/minute — high enough for normal UX, low enough to prevent accidents"
        }
    }
    
    print("\n📋 Rate Limiting Strategy:")
    for category, details in strategy.items():
        print(f"\n  {category}:")
        for key, value in details.items():
            print(f"    {key:10s}: {value}")
    
    assert True, "Strategy documented"
