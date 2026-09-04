from app.ml.model_registry import get_reranker_model
from app.schemas.ranking import RankedEvidence, RerankedEvidence

TOP_K = 5


def rerank(claim_text: str, documents: list[RankedEvidence], top_k: int = TOP_K) -> list[RerankedEvidence]:
    if not documents:
        return []

    model = get_reranker_model()
    pairs = [(claim_text, f"{doc.title} {doc.snippet}") for doc in documents]
    scores = model.predict(pairs)

    reranked = [
        RerankedEvidence(**doc.model_dump(), cross_encoder_score=float(score))
        for doc, score in zip(documents, scores)
    ]
    reranked.sort(key=lambda d: d.cross_encoder_score, reverse=True)
    return reranked[:top_k]
