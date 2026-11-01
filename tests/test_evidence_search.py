import pytest

from app.pipeline import stage3_evidence_search
from app.pipeline.stage3_evidence_search import _llm_augmented_search as _real_llm_augmented_search
from app.schemas.evidence import EvidenceDocument


def _doc(source: str, title: str) -> EvidenceDocument:
    return EvidenceDocument(source=source, title=title, url=f"https://example.com/{title}", snippet=title)


@pytest.fixture(autouse=True)
def _no_llm_query_fallback(monkeypatch):
    """Every test below calls search_all_sources with no entities, so
    build_entity_query returns "" - a weak query that would otherwise trigger
    a real LLM call (network/Ollama) on every single test in this file.
    Tests that actually exercise the fallback override this explicitly."""

    async def disabled(claim_text):
        return []

    monkeypatch.setattr("app.pipeline.stage3_evidence_search._llm_augmented_search", disabled)


async def test_default_sources_exclude_academic_apis(monkeypatch):
    async def must_not_run(query, limit=5):
        raise AssertionError("academic source queried by default")

    async def fake_news(query, limit=5):
        return [_doc("google_news", "news1")]

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "wiki1")]

    monkeypatch.setattr("app.clients.openalex_client.search", must_not_run)
    monkeypatch.setattr("app.clients.crossref_client.search", must_not_run)
    monkeypatch.setattr("app.clients.google_news_client.search", fake_news)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    docs = await stage3_evidence_search.search_all_sources("some claim")

    assert {d.source for d in docs} == {"google_news", "wikipedia"}


async def test_search_all_sources_pools_results(monkeypatch):
    async def fake_openalex(query, limit=5):
        return [_doc("openalex", "paper1")]

    async def fake_crossref(query, limit=5):
        return [_doc("crossref", "paper2")]

    async def fake_news(query, limit=5):
        return [_doc("google_news", "news1")]

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "wiki1")]

    monkeypatch.setattr("app.clients.openalex_client.search", fake_openalex)
    monkeypatch.setattr("app.clients.crossref_client.search", fake_crossref)
    monkeypatch.setattr("app.clients.google_news_client.search", fake_news)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    docs = await stage3_evidence_search.search_all_sources(
        "some claim", sources=("openalex", "crossref", "google_news", "wikipedia")
    )

    sources = {d.source for d in docs}
    assert sources == {"openalex", "crossref", "google_news", "wikipedia"}
    assert len(docs) == 4


async def test_search_all_sources_degrades_gracefully_on_failure(monkeypatch):
    async def fake_openalex(query, limit=5):
        raise TimeoutError("openalex down")

    async def fake_crossref(query, limit=5):
        return [_doc("crossref", "paper2")]

    async def fake_news(query, limit=5):
        return [_doc("google_news", "news1")]

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "wiki1")]

    monkeypatch.setattr("app.clients.openalex_client.search", fake_openalex)
    monkeypatch.setattr("app.clients.crossref_client.search", fake_crossref)
    monkeypatch.setattr("app.clients.google_news_client.search", fake_news)
    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    docs = await stage3_evidence_search.search_all_sources(
        "some claim", sources=("openalex", "crossref", "google_news", "wikipedia")
    )

    sources = {d.source for d in docs}
    assert sources == {"crossref", "google_news", "wikipedia"}
    assert len(docs) == 3


async def test_gdelt_and_semantic_scholar_are_still_callable_explicitly(monkeypatch):
    """Dropped from the default pool - GDELT is frequently unreachable
    outright and Semantic Scholar's free tier 429s intermittently even with
    a key (both confirmed live, not timeout misconfiguration) - but they
    remain wired up for explicit use if their reliability improves."""

    async def fake_gdelt(query, limit=5):
        return [_doc("gdelt", "news1")]

    async def fake_s2(query, limit=5):
        return [_doc("semantic_scholar", "paper1")]

    monkeypatch.setattr("app.clients.gdelt_client.search", fake_gdelt)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", fake_s2)

    docs = await stage3_evidence_search.search_all_sources("some claim", sources=("gdelt", "semantic_scholar"))

    assert {d.source for d in docs} == {"gdelt", "semantic_scholar"}


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
    docs = await stage3_evidence_search.search_all_sources(
        "some claim", sources=("gdelt", "semantic_scholar", "wikipedia")
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 5, f"straggler not abandoned, took {elapsed:.1f}s"
    assert {d.source for d in docs} == {"semantic_scholar", "wikipedia"}


async def test_waits_past_the_grace_period_when_nothing_has_answered(monkeypatch):
    """Returning no evidence is worse than waiting: cutting the wait short
    starved 9 of 22 requests and dropped accuracy from 87% to 40%.

    Uses two fast-race sources (gdelt/semantic_scholar) rather than
    wikipedia: wikipedia now runs its own deep-fetch pass outside this race
    entirely (see WIKIPEDIA_TASK_TIMEOUT_SECONDS), so it no longer shares a
    deadline/grace clock with these two."""
    import asyncio

    async def slow_but_useful_s2(query, limit=5):
        await asyncio.sleep(0.4)  # longer than the grace period
        return [_doc("semantic_scholar", "arrived late")]

    async def empty_wiki(query, limit=5):
        return []

    monkeypatch.setattr("app.clients.gdelt_client.search", _hanging)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", slow_but_useful_s2)
    monkeypatch.setattr("app.clients.wikipedia_client.search", empty_wiki)
    _stub_settings(monkeypatch, deadline=10, grace=0.05)

    docs = await stage3_evidence_search.search_all_sources(
        "some claim", sources=("gdelt", "semantic_scholar", "wikipedia")
    )

    assert [d.source for d in docs] == ["semantic_scholar"]


async def test_fast_failure_does_not_cut_off_a_slower_success(monkeypatch):
    """Regression test: a fast *failure* from one source in the race must not
    start the grace-period countdown and cancel another still-pending,
    about-to-succeed source. Re-adding Semantic Scholar to the default pool
    once dropped a 22-claim eval from 67% to 45% via exactly this mechanism
    (against Wikipedia, before it moved out of this race entirely - see
    WIKIPEDIA_TASK_TIMEOUT_SECONDS) - success, not mere completion, must be
    what starts the grace period."""
    import asyncio

    async def fails_fast(query, limit=5):
        raise Exception("429")  # completes almost immediately, but as a failure

    async def succeeds_slightly_slower(query, limit=5):
        await asyncio.sleep(0.05)  # comfortably longer than the grace period
        return [_doc("semantic_scholar", "real evidence")]

    async def empty_wiki(query, limit=5):
        return []

    monkeypatch.setattr("app.clients.gdelt_client.search", fails_fast)
    monkeypatch.setattr("app.clients.semantic_scholar_client.search", succeeds_slightly_slower)
    monkeypatch.setattr("app.clients.wikipedia_client.search", empty_wiki)
    _stub_settings(monkeypatch, deadline=10, grace=0.01)

    docs = await stage3_evidence_search.search_all_sources(
        "some claim", sources=("gdelt", "semantic_scholar", "wikipedia")
    )

    assert [d.source for d in docs] == ["semantic_scholar"]


async def test_weak_entity_query_triggers_llm_search_fallback(monkeypatch):
    """The exact case this exists for: "Vaccines cause autism" tags
    "Vaccines" as NORP and "autism" as nothing, so the entity query is a
    single weak word that never finds the actual controversy article."""

    async def fake_wiki(query, limit=3):
        if query == "vaccines cause autism controversy":
            return [_doc("wikipedia", "MMR vaccine and autism")]
        return [_doc("wikipedia", "generic vaccine page")]

    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.get_llm_client",
        lambda: type("Stub", (), {"generate_search_query": staticmethod(lambda claim: "vaccines cause autism controversy")}),
    )
    monkeypatch.setattr("app.pipeline.stage3_evidence_search._llm_augmented_search", _real_llm_augmented_search)

    from app.schemas.claim import ExtractedEntity

    docs = await stage3_evidence_search.search_all_sources(
        "vaccines cause autism",
        entities=[ExtractedEntity(text="vaccines", label="NORP")],
        sources=("wikipedia",),
    )

    assert any(d.title == "MMR vaccine and autism" for d in docs)


async def test_strong_entity_query_skips_llm_fallback(monkeypatch):
    """A claim with a good multi-token entity query should never pay the
    LLM latency - the fallback only exists for weak queries."""
    called = False

    async def spy(claim_text):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.pipeline.stage3_evidence_search._llm_augmented_search", spy)

    async def fake_wiki(query, limit=3):
        return [_doc("wikipedia", "Hamlet")]

    monkeypatch.setattr("app.clients.wikipedia_client.search", fake_wiki)

    from app.schemas.claim import ExtractedEntity

    await stage3_evidence_search.search_all_sources(
        "William Shakespeare wrote the play Hamlet.",
        entities=[ExtractedEntity(text="William Shakespeare", label="PERSON")],
        sources=("wikipedia",),
    )

    assert not called


def test_extract_entities_finds_named_entities():
    entities = stage3_evidence_search.extract_entities("Barack Obama was born in Hawaii in 1961.")
    labels = {e.label for e in entities}
    assert labels & {"PERSON", "GPE", "DATE"}
