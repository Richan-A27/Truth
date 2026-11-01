import httpx
import pytest

from app.clients import groq_client


class _Settings:
    def __init__(self, key, fallback):
        self.groq_api_key = key
        self.groq_api_key_fallback = fallback
        self.groq_model = "openai/gpt-oss-20b"
        self.groq_timeout_seconds = 5.0


def _response(status, *, content="ok", retry_after=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    body = {"choices": [{"message": {"content": content}}]} if status == 200 else {"error": {"message": "limit"}}
    return httpx.Response(status, json=body, headers=headers, request=httpx.Request("POST", groq_client.GROQ_URL))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    groq_client._exhausted_until.clear()
    monkeypatch.setattr(groq_client.time, "sleep", lambda s: None)


def _patch(monkeypatch, settings, responses_by_key):
    calls = []

    def fake_post(url, json, headers, timeout):
        key = headers["Authorization"].removeprefix("Bearer ")
        calls.append(key)
        return responses_by_key[key].pop(0)

    monkeypatch.setattr(groq_client, "get_settings", lambda: settings)
    monkeypatch.setattr(groq_client.httpx, "post", fake_post)
    return calls


def test_falls_back_to_second_key_when_first_is_daily_capped(monkeypatch):
    calls = _patch(
        monkeypatch,
        _Settings("primary", "backup"),
        {"primary": [_response(429, retry_after=3600)], "backup": [_response(200, content="from backup")]},
    )

    assert groq_client._generate("hi") == "from backup"
    assert calls == ["primary", "backup"]


def test_capped_key_is_skipped_on_later_calls(monkeypatch):
    calls = _patch(
        monkeypatch,
        _Settings("primary", "backup"),
        {"primary": [_response(429, retry_after=3600)], "backup": [_response(200), _response(200)]},
    )

    groq_client._generate("first")
    groq_client._generate("second")

    assert calls == ["primary", "backup", "backup"]


def test_short_rate_limit_is_retried_on_the_same_key(monkeypatch):
    calls = _patch(
        monkeypatch,
        _Settings("primary", "backup"),
        {"primary": [_response(429, retry_after=1), _response(200, content="after wait")], "backup": []},
    )

    assert groq_client._generate("hi") == "after wait"
    assert calls == ["primary", "primary"]


def test_without_fallback_a_capped_key_raises(monkeypatch):
    _patch(monkeypatch, _Settings("primary", ""), {"primary": [_response(429, retry_after=3600)]})

    with pytest.raises(httpx.HTTPStatusError):
        groq_client._generate("hi")
