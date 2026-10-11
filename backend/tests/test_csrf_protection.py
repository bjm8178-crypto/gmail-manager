import asyncio

from csrf import CSRFMiddleware, generate_csrf_token, validate_csrf_request


def test_safe_methods_and_exempt_paths_are_allowed():
    token = generate_csrf_token()
    assert validate_csrf_request("GET", "/mutate", {}, {})
    assert validate_csrf_request("POST", "/health", {}, {})
    assert validate_csrf_request("POST", "/mutate", {"csrf_token": token}, {"x-csrf-token": token})


def test_state_change_requires_matching_cookie_and_header():
    token = generate_csrf_token()
    assert not validate_csrf_request("POST", "/mutate", {}, {})
    assert not validate_csrf_request("POST", "/mutate", {"csrf_token": token}, {})
    assert not validate_csrf_request("POST", "/mutate", {"csrf_token": token}, {"x-csrf-token": "wrong"})
    assert validate_csrf_request("POST", "/mutate", {"csrf_token": token}, {"x-csrf-token": token})


def run_asgi(app, method, path, headers=()):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": method, "path": path, "headers": list(headers),
        "query_string": b"", "scheme": "http", "server": ("test", 80),
        "client": ("test", 1), "root_path": "", "http_version": "1.1",
    }
    asyncio.run(app(scope, receive, send))
    return sent


def test_middleware_returns_403_without_token():
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    sent = run_asgi(CSRFMiddleware(endpoint), "POST", "/mutate")
    assert sent[0]["status"] == 403


def test_middleware_allows_valid_token():
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    token = generate_csrf_token().encode()
    sent = run_asgi(
        CSRFMiddleware(endpoint),
        "POST",
        "/mutate",
        [(b"cookie", b"csrf_token=" + token), (b"x-csrf-token", token)],
    )
    assert sent[0]["status"] == 200
