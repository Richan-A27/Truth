from app.pipeline.stage4_bm25_retrieval import rank_by_bm25


def test_relevant_doc_ranks_above_irrelevant(sample_evidence_docs):
    ranked = rank_by_bm25("Where is the Eiffel Tower located?", sample_evidence_docs)

    by_title = {r.title: r.bm25_score for r in ranked}
    assert by_title["Eiffel Tower"] > by_title["Bicycle"]


def test_empty_documents_returns_empty_list():
    assert rank_by_bm25("some claim", []) == []
