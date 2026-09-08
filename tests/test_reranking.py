from datetime import datetime

import pytest

from app.pipeline.stage5_semantic_matching import rank_by_semantic_similarity
from app.pipeline.stage4_bm25_retrieval import rank_by_bm25
from app.pipeline.stage6_reranking import rerank
from app.schemas.ranking import RankedEvidence


@pytest.mark.integration
def test_relevant_pair_scores_higher(sample_evidence_docs):
    retrieved = rank_by_bm25("The Eiffel Tower is in Paris", sample_evidence_docs)
    ranked = rank_by_semantic_similarity("The Eiffel Tower is in Paris", retrieved)
    reranked = rerank("The Eiffel Tower is in Paris", ranked, top_k=2)

    assert reranked[0].title == "Eiffel Tower"


def test_empty_documents_returns_empty_list():
    assert rerank("some claim", []) == []


def _multi_paragraph_doc(**overrides) -> RankedEvidence:
    defaults = dict(
        source="wikipedia",
        title="Bat",
        url="https://en.wikipedia.org/wiki/Bat",
        snippet=(
            "Bats are winged mammals capable of sustained flight.\n\n"
            "Most bats navigate and hunt using echolocation and also have functional eyesight.\n\n"
            "Bat guano has historically been mined as a fertilizer."
        ),
        published_date=datetime(2020, 1, 1),
        bm25_score=1.5,
        semantic_similarity_score=0.6,
        rrf_score=0.03,
    )
    defaults.update(overrides)
    return RankedEvidence(**defaults)


@pytest.mark.integration
def test_metadata_is_preserved_through_reranking():
    """Every existing field (source, url, title, published_date, and the
    upstream retrieval scores) must survive rerank() unchanged - stage 6
    only adds cross_encoder_score and representative_paragraph, it does not
    rebuild or drop anything."""
    doc = _multi_paragraph_doc()
    reranked = rerank("Bats can see using echolocation and eyesight.", [doc])

    assert len(reranked) == 1
    result = reranked[0]
    assert result.source == doc.source
    assert result.url == doc.url
    assert result.title == doc.title
    assert result.published_date == doc.published_date
    assert result.bm25_score == doc.bm25_score
    assert result.semantic_similarity_score == doc.semantic_similarity_score
    assert result.rrf_score == doc.rrf_score


@pytest.mark.integration
def test_snippet_is_not_overwritten_by_the_representative_paragraph():
    """snippet must stay exactly as it arrived - the best-scoring chunk is
    additive, in representative_paragraph, not a replacement. Anything
    already reading .snippet (stage 7's NLI check included) must keep
    seeing the full original text."""
    doc = _multi_paragraph_doc()
    reranked = rerank("Bats can see using echolocation and eyesight.", [doc])

    assert reranked[0].snippet == doc.snippet
    assert reranked[0].representative_paragraph != doc.snippet
    assert reranked[0].representative_paragraph in doc.snippet


@pytest.mark.integration
def test_one_document_occupies_exactly_one_top_k_slot():
    """A single document with several strong-scoring paragraphs must still
    produce exactly one entry in the output, not one per paragraph."""
    doc = _multi_paragraph_doc(
        snippet=(
            "Bats can see and use echolocation to navigate.\n\n"
            "Bats have functional eyesight and are not blind.\n\n"
            "Bat vision and echolocation work together for navigation."
        )
    )
    reranked = rerank("Are bats blind or can they see?", [doc])

    assert len(reranked) == 1
    assert reranked[0].url == doc.url


@pytest.mark.integration
def test_reranking_is_deterministic_for_identical_input():
    docs = [
        _multi_paragraph_doc(),
        _multi_paragraph_doc(
            title="Yuma myotis",
            url="https://en.wikipedia.org/wiki/Yuma_myotis",
            snippet="Yuma myotis is a species of vesper bat native to western North America.",
        ),
    ]
    claim = "Bats are completely blind."

    first = rerank(claim, list(docs))
    second = rerank(claim, list(docs))

    assert [d.url for d in first] == [d.url for d in second]
    assert [d.cross_encoder_score for d in first] == [d.cross_encoder_score for d in second]
    assert [d.representative_paragraph for d in first] == [d.representative_paragraph for d in second]


@pytest.mark.integration
def test_explicit_top_k_override_is_respected():
    docs = [
        _multi_paragraph_doc(url=f"https://example.com/{i}", title=f"Doc {i}")
        for i in range(6)
    ]
    reranked = rerank("Bats are completely blind.", docs, top_k=2)
    assert len(reranked) == 2
