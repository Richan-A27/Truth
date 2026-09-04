import asyncio
import functools
import time

DEFAULT_TTL_SECONDS = 900
MAX_ENTRIES = 512


def ttl_cache(ttl_seconds: float = DEFAULT_TTL_SECONDS):
    """Cache an async source lookup by its arguments for a short window.

    Evidence lookups repeat constantly - the same claim re-checked, the same
    entity query shared by several claims, a batch evaluation run twice - and
    every repeat spends latency and free-tier quota on an answer already held.
    Wikipedia began returning 429s during testing for exactly this reason.

    Only successful calls are cached: an error should be retried next time,
    not remembered.
    """

    def decorator(fn):
        store: dict[tuple, tuple[float, object]] = {}
        locks: dict[tuple, asyncio.Lock] = {}

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()

            hit = store.get(key)
            if hit and now - hit[0] < ttl_seconds:
                return hit[1]

            # one in-flight call per key, so concurrent duplicates wait for the
            # first rather than each hitting the API
            lock = locks.setdefault(key, asyncio.Lock())
            async with lock:
                hit = store.get(key)
                if hit and time.monotonic() - hit[0] < ttl_seconds:
                    return hit[1]

                result = await fn(*args, **kwargs)

                if len(store) >= MAX_ENTRIES:
                    oldest = min(store, key=lambda k: store[k][0])
                    store.pop(oldest, None)
                    locks.pop(oldest, None)
                store[key] = (time.monotonic(), result)
                return result

        wrapper.cache_clear = store.clear
        return wrapper

    return decorator
