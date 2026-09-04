import faiss
import numpy as np

from app.ml.model_registry import get_sbert_model
from app.schemas.evidence import RetrievedEvidence
from app.schemas.ranking import RankedEvidence


def rank_by_semantic_similarity(
    claim_text: str, documents: list[RetrievedEvidence]
) -> list[RankedEvidence]:
    if not documents:
        return []

    model = get_sbert_model()
    doc_texts = [f"{doc.title} {doc.snippet}" for doc in documents]

    claim_embedding = model.encode([claim_text], normalize_embeddings=True)
    doc_embeddings = model.encode(doc_texts, normalize_embeddings=True)

    dim = doc_embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(np.asarray(doc_embeddings, dtype="float32"))

    scores, indices = index.search(np.asarray(claim_embedding, dtype="float32"), len(documents))

    score_by_doc_index = {int(idx): float(score) for idx, score in zip(indices[0], scores[0])}

    return [
        RankedEvidence(**doc.model_dump(), semantic_similarity_score=score_by_doc_index.get(i, 0.0))
        for i, doc in enumerate(documents)
    ]
