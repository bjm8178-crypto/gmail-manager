"""CSRF protection for cookie-authenticated state-changing requests."""

import secrets
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
DEFAULT_EXEMPT_PATHS = {
    "/auth/callback",
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf_request(method: str, path: str, cookies: dict[str, str], headers: dict[str, str], exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS) -> bool:
    """Return whether a request has a valid double-submit CSRF token."""
    if method.upper() in SAFE_METHODS or path in set(exempt_paths):
        return True
    cookie_token = cookies.get("csrf_token")
    header_token = headers.get("x-csrf-token")
    return bool(cookie_token and header_token and secrets.compare_digest(cookie_token, header_token))


class CSRFMiddleware:
    """Reject unsafe requests without a matching CSRF cookie and header."""

    def __init__(self, app: ASGIApp, exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS):
        self.app = app
        self.exempt_paths = set(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        cookies = {}
        for item in headers.get("cookie", "").split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookies[key] = value

        if not validate_csrf_request(scope["method"], scope["path"], cookies, headers, self.exempt_paths):
            # Diagnostic logging for 403 rejections
            method = scope["method"]
            path = scope["path"]
            cookie_token = cookies.get("csrf_token")
            header_token = headers.get("x-csrf-token")
            
            reason = "unknown"
            if not cookie_token:
                reason = "csrf_token cookie missing"
            elif not header_token:
                reason = "X-CSRF-Token header missing"
            elif not secrets.compare_digest(cookie_token, header_token):
                reason = f"csrf_token mismatch (cookie={cookie_token[:8]}... header={header_token[:8]}...)"
            
            import logging
            logger = logging.getLogger("csrf")
            logger.warning(f"[CSRF 403] {method} {path} rejected: {reason}")
            
            response = b'{"detail":"CSRF token missing or invalid"}'
            await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(response)).encode())]})
            await send({"type": "http.response.body", "body": response})
            return

        await self.app(scope, receive, send)
