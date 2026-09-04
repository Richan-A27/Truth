import asyncio

from app.core.cache import ttl_cache


async def test_repeat_call_does_not_hit_the_source():
    calls = []

    @ttl_cache()
    async def fetch(query):
        calls.append(query)
        return [query]

    assert await fetch("mars") == ["mars"]
    assert await fetch("mars") == ["mars"]
    assert calls == ["mars"]


async def test_different_arguments_are_cached_separately():
    calls = []

    @ttl_cache()
    async def fetch(query):
        calls.append(query)
        return [query]

    await fetch("mars")
    await fetch("venus")
    assert calls == ["mars", "venus"]


async def test_expired_entry_is_refetched():
    calls = []

    @ttl_cache(ttl_seconds=0.05)
    async def fetch(query):
        calls.append(query)
        return [query]

    await fetch("mars")
    await asyncio.sleep(0.1)
    await fetch("mars")
    assert calls == ["mars", "mars"]


async def test_concurrent_duplicates_share_one_call():
    """Two claims needing the same entity query must not both hit the API."""
    calls = []

    @ttl_cache()
    async def fetch(query):
        calls.append(query)
        await asyncio.sleep(0.05)
        return [query]

    await asyncio.gather(*(fetch("mars") for _ in range(5)))
    assert calls == ["mars"]


async def test_failures_are_not_cached():
    attempts = []

    @ttl_cache()
    async def flaky(query):
        attempts.append(query)
        if len(attempts) == 1:
            raise RuntimeError("throttled")
        return [query]

    try:
        await flaky("mars")
    except RuntimeError:
        pass
    assert await flaky("mars") == ["mars"]
