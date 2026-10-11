from starlette.requests import Request

from jwt_auth import create_access_token, extract_token_from_request


def make_request(headers=None):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw_headers, "query_string": b""})


def test_extracts_jwt_only_from_cookie(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    token = create_access_token(1, "user@example.com")
    request = make_request({"cookie": f"jwt_token={token}"})
    assert extract_token_from_request(request) == token


def test_authorization_header_is_not_accepted():
    request = make_request({"authorization": "Bearer should-not-be-used"})
    assert extract_token_from_request(request) is None


def test_jwt_cookie_attributes():
    from starlette.responses import RedirectResponse

    response = RedirectResponse("https://frontend.example/inbox", status_code=303)
    response.set_cookie("jwt_token", "token", max_age=604800, httponly=True, secure=True, samesite="lax")
    cookie = response.headers["set-cookie"]
    assert "jwt_token=token" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=604800" in cookie
