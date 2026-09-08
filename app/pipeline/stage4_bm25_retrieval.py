from rank_bm25 import BM25Okapi

from app.core.tokenize import stem_tokenize
from app.schemas.evidence import EvidenceDocument, RetrievedEvidence


def rank_by_bm25(claim_text: str, documents: list[EvidenceDocument]) -> list[RetrievedEvidence]:
    if not documents:
        return []

    corpus = [stem_tokenize(f"{doc.title} {doc.snippet}") for doc in documents]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(stem_tokenize(claim_text))

    return [
        RetrievedEvidence(**doc.model_dump(), bm25_score=float(score))
        for doc, score in zip(documents, scores)
    ]
