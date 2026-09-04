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


def test_extract_entities_finds_named_entities():
    entities = stage3_evidence_search.extract_entities("Barack Obama was born in Hawaii in 1961.")
    labels = {e.label for e in entities}
    assert labels & {"PERSON", "GPE", "DATE"}
