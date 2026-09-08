from app.ml.model_registry import get_reranker_model, get_sentencizer
from app.schemas.ranking import RankedEvidence, RerankedEvidence

# Dynamic top-k: keep a tight top 3 when the winner is clearly separated
# from the rest, widen to top 8 when scores are bunched together and
# cutting to 3 would risk discarding evidence that's genuinely competitive.
# Cross-encoder scores in this pipeline have ranged roughly -5 to +10 -
# a same-magnitude gap between rank 1 and rank 3 is a real separation, not
# scoring noise.
MIN_TOP_K = 3
MAX_TOP_K = 8
STRONG_WINNER_MARGIN = 2.0

# Scores are rounded to this many decimal places before comparing the
# rank-1-to-rank-3 gap. Without it, two calls carrying the same underlying
# relevance could differ in a far decimal place - floating-point summation
# in the model's forward pass is sensitive to batch order - and
# occasionally land on opposite sides of STRONG_WINNER_MARGIN, changing
# top_k for a difference with no real meaning.
SCORE_PRECISION = 3

# A cap on the single best-scoring chunk kept per document - long enough to
# carry a full sentence or two, short enough to stay a clean claim/evidence
# pair for whatever reads it next.
MAX_CHUNK_CHARS = 800


def _chunk(text: str) -> list[str]:
    """Split a document's text into paragraph-sized pieces to score
    independently, instead of one blob whose average obscures whichever
    single part actually answers the claim - confirmed live: the
    deep-fetched "Bat" article scored -0.26 as a whole snippet despite
    containing an on-topic vision paragraph.

    Splits on paragraph breaks (present in Wikipedia's deep-fetched text,
    see wikipedia_client.py) when there are any; falls back to sentences
    for the single-block abstracts and headlines the other sources return,
    so short documents still get their best sentence found rather than
    being scored as one unsplit chunk.
    """
    if not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs
    nlp = get_sentencizer()
    sentences = [s.text.strip() for s in nlp(text).sents if s.text.strip()]
    return sentences or [text]


def _best_chunk_per_document(
    pairs: list[tuple[str, str]], owner_doc_index: list[int], scores, num_documents: int
) -> tuple[list[float], list[str]]:
    """Reduce per-chunk scores down to one best (score, chunk) pair per
    document. This is what guarantees a document can never occupy more than
    one Top-K slot just because several of its paragraphs score well: the
    return value is always exactly `num_documents` long, indexed by
    document - paragraphs never become independent ranking candidates."""
    best_score = [float("-inf")] * num_documents
    best_chunk = [""] * num_documents
    for i, doc_index in enumerate(owner_doc_index):
        score = float(scores[i])
        if score > best_score[doc_index]:
            best_score[doc_index] = score
            best_chunk[doc_index] = pairs[i][1]
    return best_score, best_chunk


def _dynamic_top_k(sorted_scores: list[float]) -> int:
    if len(sorted_scores) <= MIN_TOP_K:
        return len(sorted_scores)
    rounded = [round(s, SCORE_PRECISION) for s in sorted_scores]
    margin = rounded[0] - rounded[MIN_TOP_K - 1]
    return MIN_TOP_K if margin >= STRONG_WINNER_MARGIN else min(MAX_TOP_K, len(sorted_scores))


def rerank(claim_text: str, documents: list[RankedEvidence], top_k: int | None = None) -> list[RerankedEvidence]:
    if not documents:
        return []

    model = get_reranker_model()

    doc_chunks = [_chunk(f"{doc.title}. {doc.snippet}") for doc in documents]
    pairs: list[tuple[str, str]] = []
    owner_doc_index: list[int] = []
    for doc_index, chunks in enumerate(doc_chunks):
        for chunk in chunks:
            pairs.append((claim_text, chunk))
            owner_doc_index.append(doc_index)

    raw_scores = model.predict(pairs) if pairs else []
    best_score, best_chunk = _best_chunk_per_document(pairs, owner_doc_index, raw_scores, len(documents))

    # One RerankedEvidence per input document (never per paragraph) - all
    # of `documents[i]`'s original fields (source, url, title,
    # published_date, bm25_score, semantic_similarity_score, rrf_score)
    # pass through via model_dump() untouched. `snippet` is preserved as-is;
    # the best-scoring chunk is additive via representative_paragraph, so
    # every existing reader (stage 7's NLI check, the API response, stage
    # 9's explanation) keeps seeing exactly what it always has.
    reranked = [
        RerankedEvidence(
            **doc.model_dump(),
            cross_encoder_score=best_score[i],
            representative_paragraph=best_chunk[i][:MAX_CHUNK_CHARS],
        )
        for i, doc in enumerate(documents)
    ]

    reranked.sort(key=lambda d: d.cross_encoder_score, reverse=True)
    keep = top_k if top_k is not None else _dynamic_top_k([d.cross_encoder_score for d in reranked])
    return reranked[:keep]
