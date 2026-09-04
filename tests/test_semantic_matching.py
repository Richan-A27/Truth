import pytest

from app.pipeline.stage4_bm25_retrieval import rank_by_bm25
from app.pipeline.stage5_semantic_matching import rank_by_semantic_similarity


@pytest.mark.integration
def test_semantically_similar_doc_ranks_first(sample_evidence_docs):
    retrieved = rank_by_bm25("A famous landmark in Paris", sample_evidence_docs)
    ranked = rank_by_semantic_similarity("A famous landmark in Paris", retrieved)

    top = max(ranked, key=lambda r: r.semantic_similarity_score)
    assert top.title == "Eiffel Tower"


def test_empty_documents_returns_empty_list():
    assert rank_by_semantic_similarity("some claim", []) == []
