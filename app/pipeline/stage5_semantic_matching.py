import faiss
import numpy as np

from app.ml.model_registry import get_sbert_model, get_sentencizer
from app.schemas.evidence import RetrievedEvidence
from app.schemas.ranking import RankedEvidence

# RRF's smoothing constant, from the original paper (Cormack et al. 2009).
# BM25 scores and cosine similarities live on different, incomparable
# scales - averaging the raw numbers would let whichever one happens to
# have the wider numeric range dominate. RRF sidesteps that by fusing each
# document's RANK within each list instead of its raw score, with k large
# enough that one ranker's #1 pick doesn't automatically outweigh the
# other's #2, but still small enough that rank position dominates.
RRF_K = 60


def _whole_snippet_embeddings(claim_text: str, documents: list[RetrievedEvidence]) -> tuple[np.ndarray, np.ndarray]:
    model = get_sbert_model()
    doc_texts = [f"{doc.title} {doc.snippet}" for doc in documents]
    claim_embedding = np.asarray(model.encode([claim_text], normalize_embeddings=True), dtype="float32")
    doc_embeddings = np.asarray(model.encode(doc_texts, normalize_embeddings=True), dtype="float32")
    return claim_embedding, doc_embeddings


def _whole_snippet_similarity(claim_embedding: np.ndarray, doc_embeddings: np.ndarray) -> list[float]:
    dim = doc_embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(doc_embeddings)
    scores, indices = index.search(claim_embedding, doc_embeddings.shape[0])
    score_by_doc_index = {int(idx): float(score) for idx, score in zip(indices[0], scores[0])}
    return [score_by_doc_index.get(i, 0.0) for i in range(doc_embeddings.shape[0])]


def _ranks_from_scores(scores: list[float]) -> list[int]:
    """1-indexed rank of each score within the list, highest score first."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranks = [0] * len(scores)
    for rank, i in enumerate(order, start=1):
        ranks[i] = rank
    return ranks


def reciprocal_rank_fusion(bm25_scores: list[float], sbert_scores: list[float], k: int = RRF_K) -> list[float]:
    bm25_ranks = _ranks_from_scores(bm25_scores)
    sbert_ranks = _ranks_from_scores(sbert_scores)
    return [1.0 / (k + bm25_ranks[i]) + 1.0 / (k + sbert_ranks[i]) for i in range(len(bm25_scores))]


def _best_sentence_similarity(model, claim_embedding: np.ndarray, sentences: list[str]) -> float:
    """Max cosine similarity between the claim and any single sentence,
    rather than one embedding of the whole title+snippet blob - a document
    with one perfectly relevant sentence buried among several irrelevant
    ones (a long deep-fetched passage, say) scores on the strength of that
    sentence instead of being diluted by the average of the whole thing."""
    if not sentences:
        return 0.0
    sentence_embeddings = np.asarray(model.encode(sentences, normalize_embeddings=True), dtype="float32")
    return float((sentence_embeddings @ claim_embedding[0]).max())


def rank_by_semantic_similarity(
    claim_text: str, documents: list[RetrievedEvidence]
) -> list[RankedEvidence]:
    if not documents:
        return []

    model = get_sbert_model()
    claim_embedding, doc_embeddings = _whole_snippet_embeddings(claim_text, documents)
    whole_snippet_scores = _whole_snippet_similarity(claim_embedding, doc_embeddings)

    bm25_scores = [doc.bm25_score for doc in documents]
    rrf_scores = reciprocal_rank_fusion(bm25_scores, whole_snippet_scores)

    nlp = get_sentencizer()
    # one encode call for every document's sentences instead of one per
    # document - per-call overhead dominates for these short inputs
    all_sentences: list[str] = []
    spans: list[tuple[int, int]] = []
    for doc in documents:
        sentences = [s.text.strip() for s in nlp(f"{doc.title}. {doc.snippet}").sents if s.text.strip()]
        spans.append((len(all_sentences), len(all_sentences) + len(sentences)))
        all_sentences.extend(sentences)
    sims = np.zeros(0, dtype="float32")
    if all_sentences:
        sims = np.asarray(model.encode(all_sentences, normalize_embeddings=True, batch_size=64), dtype="float32") @ claim_embedding[0]
    sentence_scores = [float(sims[a:b].max()) if b > a else 0.0 for a, b in spans]

    ranked = [
        RankedEvidence(
            **doc.model_dump(),
            semantic_similarity_score=sentence_scores[i],
            rrf_score=rrf_scores[i],
        )
        for i, doc in enumerate(documents)
    ]
    ranked.sort(key=lambda d: d.rrf_score, reverse=True)
    return ranked
