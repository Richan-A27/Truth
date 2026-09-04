import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


def retry_external_call():
    """Retry policy for calls to free/rate-limited third-party APIs
    (GDELT, Semantic Scholar, Wikipedia): one retry on network errors,
    429s, and 5xx responses; no retry on other 4xx (a malformed request
    won't succeed on a second try)."""
    return retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
