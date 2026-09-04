import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed


def _is_retryable(exc: BaseException) -> bool:
    # A timeout has already consumed the caller's latency budget, and a 429
    # means the source is throttling us - neither clears within the retry
    # window, so both are left to the evidence deadline to handle.
    if isinstance(exc, (httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def retry_external_call():
    """Retry policy for calls to free/rate-limited third-party APIs
    (GDELT, Semantic Scholar, Wikipedia): one fast retry on a dropped
    connection or 5xx. The wait is deliberately short so a retry can still
    finish inside the evidence-gathering deadline."""
    return retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(0.2),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
