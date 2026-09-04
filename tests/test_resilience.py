import httpx

from app.core.resilience import _is_retryable


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_timeout_is_retryable():
    assert _is_retryable(httpx.TimeoutException("timed out")) is True


def test_connect_error_is_retryable():
    assert _is_retryable(httpx.ConnectError("connection refused")) is True


def test_429_is_retryable():
    assert _is_retryable(_status_error(429)) is True


def test_5xx_is_retryable():
    assert _is_retryable(_status_error(503)) is True


def test_404_is_not_retryable():
    assert _is_retryable(_status_error(404)) is False


def test_400_is_not_retryable():
    assert _is_retryable(_status_error(400)) is False


def test_unrelated_exception_is_not_retryable():
    assert _is_retryable(ValueError("bad input")) is False
