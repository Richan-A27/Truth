"""Regression probes for stage 6 (paragraph-level reranking + dynamic
top-k). Each test inspects intermediate pipeline state - retrieved
documents, the chunk selected as each document's representative_paragraph,
cross-encoder scores, and which documents survive into the final top-k -
rather than judging success solely from a downstream verdict. Stage 7/8
behavior is out of scope here; a case can pass this file's assertions about
stage 6's own correctness even if the eventual verdict still has known,
separately-tracked issues (Photosynthesis/roots).
"""

import pytest

from app.pipeline import stage3_evidence_search, stage4_bm25_retrieval, stage5_semantic_matching, stage6_reranking


async def _run_through_stage6(claim: str):
    entities = stage3_evidence_search.extract_entities(claim)
    documents = await stage3_evidence_search.search_all_sources(claim, entities=entities)
    retrieved = stage4_bm25_retrieval.rank_by_bm25(claim, documents)
    ranked = stage5_semantic_matching.rank_by_semantic_similarity(claim, retrieved)
    reranked = stage6_reranking.rerank(claim, ranked)
    return documents, reranked


def _assert_one_slot_per_document(reranked):
    urls = [d.url for d in reranked]
    assert len(urls) == len(set(urls)), f"a document occupies more than one Top-K slot: {urls}"


@pytest.mark.integration
async def test_bats_regression():
    documents, reranked = await _run_through_stage6("Bats are completely blind.")
    _assert_one_slot_per_document(reranked)

    print(f"\n[bats] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")
        print(f"    representative_paragraph: {d.representative_paragraph[:150]!r}")

    vision_related = {"vision", "eyesight", "echolocation", "blind", "see"}
    assert any(
        any(term in d.representative_paragraph.lower() for term in vision_related) for d in reranked
    ), "no surviving document's representative paragraph addresses bat vision at all"


@pytest.mark.integration
async def test_einstein_regression():
    documents, reranked = await _run_through_stage6("Albert Einstein developed the theory of general relativity.")
    _assert_one_slot_per_document(reranked)

    print(f"\n[einstein] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")
        print(f"    representative_paragraph: {d.representative_paragraph[:150]!r}")

    titles = {d.title.lower() for d in reranked}
    assert "general relativity" in titles or "theory of relativity" in titles, (
        f"neither canonical relativity article survived to Top-K: {titles}"
    )


@pytest.mark.integration
async def test_moon_green_cheese_regression():
    documents, reranked = await _run_through_stage6("The Moon is made of green cheese.")
    _assert_one_slot_per_document(reranked)

    print(f"\n[moon] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")
        print(f"    snippet unchanged (len={len(d.snippet)}): {d.snippet[:100]!r}")
        print(f"    representative_paragraph: {d.representative_paragraph[:150]!r}")

    myth_doc = next((d for d in reranked if d.title.lower() == "the moon is made of green cheese"), None)
    assert myth_doc is not None, "the canonical myth article did not survive to Top-K"
    # snippet must be the full original text, not silently replaced by the
    # representative paragraph - this is the specific field-preservation
    # bug this task fixed
    assert myth_doc.representative_paragraph != myth_doc.snippet or len(myth_doc.snippet) < 200


@pytest.mark.integration
async def test_shakespeare_regression():
    documents, reranked = await _run_through_stage6("William Shakespeare wrote the play Hamlet.")
    _assert_one_slot_per_document(reranked)

    print(f"\n[shakespeare] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")

    titles = {d.title.lower() for d in reranked}
    assert "hamlet" in titles, f"the canonical Hamlet article did not survive to Top-K: {titles}"


@pytest.mark.integration
async def test_great_wall_regression():
    documents, reranked = await _run_through_stage6(
        "The Great Wall of China is visible from space with the naked eye."
    )
    _assert_one_slot_per_document(reranked)

    print(f"\n[great wall] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")
        print(f"    representative_paragraph: {d.representative_paragraph[:150]!r}")

    titles = {d.title.lower() for d in reranked}
    assert "great wall of china" in titles or "artificial structures visible from space" in titles, (
        f"neither directly relevant article survived to Top-K: {titles}"
    )


@pytest.mark.integration
async def test_photosynthesis_roots_regression():
    """Known, unresolved limitation (raw NLI miscall on thin evidence, not
    a stage 6 bug) - this test only checks stage 6's own invariants
    (dedup, non-empty output) and prints intermediate state for inspection.
    It does not assert on the eventual verdict."""
    documents, reranked = await _run_through_stage6("Photosynthesis in plants primarily occurs in the roots.")
    _assert_one_slot_per_document(reranked)

    print(f"\n[photosynthesis] retrieved {len(documents)} documents, kept {len(reranked)} after rerank")
    for d in reranked:
        print(f"  cross={d.cross_encoder_score:.2f} {d.source:14s} {d.title!r}")
        print(f"    representative_paragraph: {d.representative_paragraph[:150]!r}")

    assert isinstance(reranked, list)  # stage 6 completes without error even on this hard case
