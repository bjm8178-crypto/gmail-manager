from security_headers import SecurityHeadersMiddleware


def run_asgi(app):
    import asyncio
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": "GET", "path": "/health", "headers": [],
        "query_string": b"", "scheme": "https", "server": ("test", 443),
        "client": ("test", 1), "root_path": "", "http_version": "1.1",
    }
    asyncio.run(app(scope, receive, send))
    return sent


def test_security_headers_are_added_to_response():
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    start = run_asgi(SecurityHeadersMiddleware(endpoint))[0]
    headers = {key.decode(): value.decode() for key, value in start["headers"]}
    assert headers["content-security-policy"] == "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    assert headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
