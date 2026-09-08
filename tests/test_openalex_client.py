import pytest

from app.clients.openalex_client import _reconstruct_abstract


def test_reconstructs_words_in_position_order():
    # "the paper studies mars" scrambled into an inverted index
    index = {"the": [0], "paper": [1], "studies": [2], "mars": [3]}
    assert _reconstruct_abstract(index) == "the paper studies mars"


def test_handles_repeated_words_at_multiple_positions():
    index = {"the": [0, 2], "sun": [1], "and": [3], "moon": [4]}
    assert _reconstruct_abstract(index) == "the sun the and moon"


def test_empty_or_missing_index_returns_empty_string():
    assert _reconstruct_abstract(None) == ""
    assert _reconstruct_abstract({}) == ""


def test_truncates_very_long_abstracts():
    index = {f"word{i}": [i] for i in range(300)}
    result = _reconstruct_abstract(index)
    assert len(result.split()) == 200


@pytest.mark.integration
async def test_live_search_returns_evidence_documents():
    from app.clients.openalex_client import search

    docs = await search("climate change")
    assert len(docs) > 0
    assert all(d.source == "openalex" for d in docs)
    assert all(d.title for d in docs)
