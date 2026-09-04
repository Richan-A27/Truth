import pytest

from app.pipeline.stage5_semantic_matching import rank_by_semantic_similarity
from app.pipeline.stage4_bm25_retrieval import rank_by_bm25
from app.pipeline.stage6_reranking import rerank


@pytest.mark.integration
def test_relevant_pair_scores_higher(sample_evidence_docs):
    retrieved = rank_by_bm25("The Eiffel Tower is in Paris", sample_evidence_docs)
    ranked = rank_by_semantic_similarity("The Eiffel Tower is in Paris", retrieved)
    reranked = rerank("The Eiffel Tower is in Paris", ranked, top_k=2)

    assert reranked[0].title == "Eiffel Tower"


def test_empty_documents_returns_empty_list():
    assert rerank("some claim", []) == []
