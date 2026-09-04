"""Lazy-loaded singletons for all local ML models.

Loaded once (via `load_all()` at FastAPI startup) so requests never pay
model-load latency. Each getter also lazy-loads on first call as a fallback
(e.g. for tests that import a single stage directly).
"""

import spacy
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.ml.device import get_device

_spacy_nlp: spacy.language.Language | None = None
_sbert_model: SentenceTransformer | None = None
_reranker_model: CrossEncoder | None = None
_nli_model: CrossEncoder | None = None

SPACY_MODEL_NAME = "en_core_web_sm"
SBERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-base"

# label order for the nli-deberta-v3-base cross-encoder output logits
NLI_LABELS = ["contradiction", "entailment", "neutral"]


def get_spacy_nlp() -> spacy.language.Language:
    global _spacy_nlp
    if _spacy_nlp is None:
        _spacy_nlp = spacy.load(SPACY_MODEL_NAME)
    return _spacy_nlp


def get_sbert_model() -> SentenceTransformer:
    global _sbert_model
    if _sbert_model is None:
        _sbert_model = SentenceTransformer(SBERT_MODEL_NAME, device=get_device())
    return _sbert_model


def get_reranker_model() -> CrossEncoder:
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = CrossEncoder(RERANKER_MODEL_NAME, device=get_device())
    return _reranker_model


def get_nli_model() -> CrossEncoder:
    global _nli_model
    if _nli_model is None:
        _nli_model = CrossEncoder(NLI_MODEL_NAME, device=get_device())
    return _nli_model


def load_all() -> None:
    """Eagerly load every model. Call once during FastAPI lifespan startup."""
    get_spacy_nlp()
    get_sbert_model()
    get_reranker_model()
    get_nli_model()


def models_loaded() -> bool:
    return all(
        m is not None for m in (_spacy_nlp, _sbert_model, _reranker_model, _nli_model)
    )
