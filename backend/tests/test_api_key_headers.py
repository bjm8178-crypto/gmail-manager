import asyncio

import ai_router


class FakeResponse:
    status_code = 200
    headers = {}
    text = ""

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


def test_gemini_api_key_is_sent_in_header_not_url(monkeypatch):
    monkeypatch.setattr(ai_router, "GEMINI_API_KEYS", ["AIza-test-secret"])
    router = ai_router.AIRouter()
    fake = FakeClient()
    router.async_client = fake
    asyncio.run(router._call_gemini("hello"))
    url, kwargs = fake.calls[0]
    assert "?key=" not in url
    assert kwargs["headers"]["x-goog-api-key"] == "AIza-test-secret"
