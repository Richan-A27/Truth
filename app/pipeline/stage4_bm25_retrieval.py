import re

from rank_bm25 import BM25Okapi

from app.schemas.evidence import EvidenceDocument, RetrievedEvidence

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def rank_by_bm25(claim_text: str, documents: list[EvidenceDocument]) -> list[RetrievedEvidence]:
    if not documents:
        return []

    corpus = [_tokenize(f"{doc.title} {doc.snippet}") for doc in documents]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(claim_text))

    return [
        RetrievedEvidence(**doc.model_dump(), bm25_score=float(score))
        for doc, score in zip(documents, scores)
    ]
