import pytest

from app.pipeline import stage3_evidence_search
from app.schemas.evidence import EvidenceDocument


def _doc(source: str, title: str) -> EvidenceDocument:
    return EvidenceDocument(source=source, title=title, url=f"https://example.com/{title}", snippet=title)


async def test_search_all_sources_pools_results(monkeypatch):
    async def fake_gdelt(query, limit=5):
        return [_doc("gdelt", "news1")]

    async def fake_s2(query, limit=5):
        return [_doc("semantic_scholar", "paper1")]

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "wiki1")]

    monkeypatch.setattr("app.clients.gdelt_client.search", fake_gdelt)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", fake_s2)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    docs = await stage3_evidence_search.search_all_sources("some claim")

    sources = {d.source for d in docs}
    assert sources == {"gdelt", "semantic_scholar", "wikipedia"}
    assert len(docs) == 3


async def test_search_all_sources_degrades_gracefully_on_failure(monkeypatch):
    async def fake_gdelt(query, limit=5):
        raise TimeoutError("gdelt down")

    async def fake_s2(query, limit=5):
        return [_doc("semantic_scholar", "paper1")]

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "wiki1")]

    monkeypatch.setattr("app.clients.gdelt_client.search", fake_gdelt)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", fake_s2)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    docs = await stage3_evidence_search.search_all_sources("some claim")

    sources = {d.source for d in docs}
    assert sources == {"semantic_scholar", "wikipedia"}
    assert len(docs) == 2


def _stub_settings(monkeypatch, *, deadline: float, grace: float):
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.get_settings",
        lambda: type("S", (), {"evidence_deadline_seconds": deadline, "evidence_grace_seconds": grace})(),
    )


async def _hanging(query, limit=5):
    import asyncio

    await asyncio.sleep(30)
    return [_doc("gdelt", "never arrives")]


async def test_slow_source_is_abandoned_once_another_answers(monkeypatch):
    """A source that hangs must not hold up the verdict: GDELT was measured
    taking 17.8s to return a 429."""
    import time

    async def fast_wiki(query, limit=5):
        return [_doc("wikipedia", "wiki1")]

    async def fast_s2(query, limit=5):
        return [_doc("semantic_scholar", "paper1")]

    monkeypatch.setattr("app.clients.gdelt_client.search", _hanging)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", fast_s2)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fast_wiki)
    _stub_settings(monkeypatch, deadline=10, grace=0.1)

    started = time.perf_counter()
    docs = await stage3_evidence_search.search_all_sources("some claim")
    elapsed = time.perf_counter() - started

    assert elapsed < 5, f"straggler not abandoned, took {elapsed:.1f}s"
    assert {d.source for d in docs} == {"semantic_scholar", "wikipedia"}


async def test_waits_past_the_grace_period_when_nothing_has_answered(monkeypatch):
    """Returning no evidence is worse than waiting: cutting the wait short
    starved 9 of 22 requests and dropped accuracy from 87% to 40%."""
    import asyncio

    async def slow_but_useful_wiki(query, limit=5):
        await asyncio.sleep(0.4)  # longer than the grace period
        return [_doc("wikipedia", "arrived late")]

    monkeypatch.setattr("app.clients.gdelt_client.search", _hanging)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", _hanging)
    monkeypatch.setattr("app.clients.wikipedia_client.search", slow_but_useful_wiki)
    _stub_settings(monkeypatch, deadline=10, grace=0.05)

    docs = await stage3_evidence_search.search_all_sources("some claim")

    assert [d.source for d in docs] == ["wikipedia"]


def test_extract_entities_finds_named_entities():
    entities = stage3_evidence_search.extract_entities("Barack Obama was born in Hawaii in 1961.")
    labels = {e.label for e in entities}
    assert labels & {"PERSON", "GPE", "DATE"}
