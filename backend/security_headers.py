"""Security response headers middleware."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


SECURITY_HEADERS = {
    b"content-security-policy": b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    b"strict-transport-security": b"max-age=31536000; includeSubDomains",
    b"x-frame-options": b"DENY",
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message):
            if message["type"] == "http.response.start":
                existing = list(message.get("headers", []))
                existing_names = {key.lower() for key, _ in existing}
                existing.extend((key, value) for key, value in SECURITY_HEADERS.items() if key not in existing_names)
                message = {**message, "headers": existing}
            await send(message)

        await self.app(scope, receive, send_with_headers)
