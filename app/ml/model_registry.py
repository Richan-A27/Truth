"""Lazy-loaded singletons for all local ML models.

Loaded once (via `load_all()` at FastAPI startup) so requests never pay
model-load latency. Each getter also lazy-loads on first call as a fallback
(e.g. for tests that import a single stage directly).
"""

import spacy
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.config import get_settings
from app.ml.device import get_device

_spacy_nlp: spacy.language.Language | None = None
_sentencizer: spacy.language.Language | None = None
_sbert_model: SentenceTransformer | None = None
_reranker_model: CrossEncoder | None = None
_nli_models: dict[str, CrossEncoder] = {}

SPACY_MODEL_NAME = "en_core_web_sm"
SBERT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Two selectable NLI backends (see app.config.Settings.nli_model) so the
# fact-verification variant can be A/B'd against the current one with
# everything else in stage 7 held identical. Label ORDER differs between
# them - the fact-verification checkpoint's own config.json says
# {0: entailment, 1: neutral, 2: contradiction}, not the same order as the
# current model - so callers must always index via get_nli_labels(variant)
# for whichever variant they actually requested, never a bare constant.
NLI_MODEL_VARIANTS = {
    # Generic NLI, no fact-verification-specific training. Has a measured,
    # documented bias toward "contradiction" on merely-unrelated text (see
    # stage7_nli_verification.py) that several heuristics compensate for.
    "current": "cross-encoder/nli-deberta-v3-base",
    # Same architecture family and size class (DeBERTa-v3-base, 12 layers,
    # 768 hidden) as "current", fine-tuned on MNLI+FEVER+ANLI - FEVER being
    # an actual claim-vs-Wikipedia-evidence fact-verification dataset, the
    # closest free/public match to this pipeline's own task. Revision
    # pinned so the A/B comparison stays reproducible.
    "fact_verification": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
}
NLI_MODEL_REVISIONS = {
    "fact_verification": "6f5cf0a2b59cabb106aca4c287eed12e357e90eb",
}
NLI_LABELS_BY_VARIANT = {
    "current": ["contradiction", "entailment", "neutral"],
    "fact_verification": ["entailment", "neutral", "contradiction"],
}


def get_spacy_nlp() -> spacy.language.Language:
    """Full pipeline - needed for named entity recognition."""
    global _spacy_nlp
    if _spacy_nlp is None:
        _spacy_nlp = spacy.load(SPACY_MODEL_NAME)
    return _spacy_nlp


def get_sentencizer() -> spacy.language.Language:
    """Rule-based sentence splitter.

    Splitting evidence into sentences does not need the tagger, parser or
    NER that en_core_web_sm runs: measured at 30.6 ms per document versus
    0.1 ms here, paid once per evidence item on every request.
    """
    global _sentencizer
    if _sentencizer is None:
        _sentencizer = spacy.blank("en")
        _sentencizer.add_pipe("sentencizer")
    return _sentencizer


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


def get_nli_model(variant: str | None = None) -> CrossEncoder:
    """`variant` defaults to settings.nli_model ("current" or
    "fact_verification") but can be passed explicitly to load/use both side
    by side in the same process - the A/B comparison script does exactly
    that rather than restarting the server to switch backends. Each variant
    is cached independently so requesting both only pays the load cost once
    per variant, not once per call."""
    variant = variant or get_settings().nli_model
    if variant not in _nli_models:
        model_name = NLI_MODEL_VARIANTS[variant]
        revision = NLI_MODEL_REVISIONS.get(variant)
        kwargs = {"revision": revision} if revision else {}
        _nli_models[variant] = CrossEncoder(model_name, device=get_device(), **kwargs)
    return _nli_models[variant]


def get_nli_labels(variant: str | None = None) -> list[str]:
    """Label order is model-specific - see NLI_LABELS_BY_VARIANT's comment.
    Always fetch labels through this function for whichever variant you
    requested from get_nli_model(); never assume the order matches between
    variants."""
    variant = variant or get_settings().nli_model
    return NLI_LABELS_BY_VARIANT[variant]


def load_all(warm: bool = True) -> None:
    """Eagerly load every model. Call once during FastAPI lifespan startup.

    Loading the weights is not enough: the first real inference on each model
    costs far more than later ones (measured at ~2.4s across the three
    transformers, versus ~0.45s once warm), so a throwaway pass is run here
    to keep that cost out of the first request.
    """
    get_spacy_nlp()
    get_sentencizer()
    get_sbert_model()
    get_reranker_model()
    get_nli_model()
    if warm:
        _warm_up()


def _warm_up() -> None:
    pair = [("Paris is the capital of France.", "France's capital is Paris.")]
    get_spacy_nlp()("Warm up the tagger and parser.")
    get_sbert_model().encode(["warm up"], normalize_embeddings=True)
    get_reranker_model().predict(pair)
    get_nli_model().predict(pair)


def models_loaded() -> bool:
    return all(
        m is not None for m in (_spacy_nlp, _sentencizer, _sbert_model, _reranker_model)
    ) and bool(_nli_models)
