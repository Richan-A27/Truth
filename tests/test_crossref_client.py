import pytest


@pytest.mark.integration
async def test_search_returns_documents_with_titles():
    from app.clients.crossref_client import search

    docs = await search("bat echolocation vision", limit=5)
    assert docs
    assert all(d.title for d in docs)
    assert all(d.source == "crossref" for d in docs)


@pytest.mark.integration
async def test_works_without_an_abstract_fall_back_to_title():
    from app.clients.crossref_client import search

    docs = await search("covid vaccine dna", limit=5)
    assert docs
    for d in docs:
        assert d.snippet  # never empty, even when CrossRef has no abstract
