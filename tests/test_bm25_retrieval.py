from app.pipeline.stage4_bm25_retrieval import rank_by_bm25
from app.schemas.evidence import EvidenceDocument


def test_relevant_doc_ranks_above_irrelevant(sample_evidence_docs):
    ranked = rank_by_bm25("Where is the Eiffel Tower located?", sample_evidence_docs)

    by_title = {r.title: r.bm25_score for r in ranked}
    assert by_title["Eiffel Tower"] > by_title["Bicycle"]


def test_empty_documents_returns_empty_list():
    assert rank_by_bm25("some claim", []) == []


def test_stemming_improves_ranking_for_inflected_terms():
    # 3 docs, not 2: rank_bm25's IDF formula degenerates to 0 for every
    # document in a 2-doc corpus in some term-overlap configurations - not a
    # stemming issue, just BM25Okapi needing enough documents to compute a
    # meaningful IDF.
    docs = [
        EvidenceDocument(
            source="wikipedia", title="Vaccine misinformation",
            url="https://example.com/1", snippet="Common myths about vaccination and autism.",
        ),
        EvidenceDocument(
            source="wikipedia", title="Bicycle",
            url="https://example.com/2", snippet="A bicycle is a human-powered vehicle.",
        ),
        EvidenceDocument(
            source="wikipedia", title="Filler",
            url="https://example.com/3", snippet="This is unrelated filler text about cooking recipes.",
        ),
    ]
    ranked = rank_by_bm25("Vaccines cause autism.", docs)
    by_title = {r.title: r.bm25_score for r in ranked}
    assert by_title["Vaccine misinformation"] > by_title["Bicycle"]
