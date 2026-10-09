"""
Deployment smoke test: verify critical modules can be imported.
Catches missing modules before production deployment.
"""
import sys
from pathlib import Path

# Add backend to path for import testing
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))


def test_v2_routing_import():
    """Critical: v2_routing must be importable in production."""
    try:
        from v2_routing import route_email_with_v2
        assert callable(route_email_with_v2), "route_email_with_v2 must be callable"
    except ImportError as e:
        raise AssertionError(f"DEPLOYMENT BLOCKER: v2_routing import failed: {e}")


def test_core_dependencies_import():
    """Verify v2_routing dependencies are available."""
    modules_to_test = [
        'decision_policy',
        'ai_response_schema',
        'logger_setup',
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
        except ImportError as e:
            raise AssertionError(f"DEPLOYMENT BLOCKER: {module_name} import failed: {e}")


def test_optional_predict_module():
    """predict.py is optional (ML model may be missing), but import should not crash."""
    try:
        from predict import predict_email
        # If import succeeds, verify it's callable
        assert callable(predict_email), "predict_email must be callable"
    except FileNotFoundError:
        # Expected when model file is missing in production
        pass
    except ImportError:
        # Also acceptable - module or dependencies missing
        pass


def test_gmail_pipeline_imports():
    """Verify main pipeline module imports successfully."""
    try:
        import gmail
        assert hasattr(gmail, '_analyze_one'), "gmail._analyze_one must exist"
    except ImportError as e:
        raise AssertionError(f"DEPLOYMENT BLOCKER: gmail.py import failed: {e}")


def test_ai_router_import():
    """Verify AI router is importable."""
    try:
        from ai_router import AIRouter
        assert AIRouter is not None
    except ImportError as e:
        raise AssertionError(f"DEPLOYMENT BLOCKER: ai_router import failed: {e}")
