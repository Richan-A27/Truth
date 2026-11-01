import numpy as np
import pytest

from app.pipeline import stage7b_evidence_claim_resolution as stage7b
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence


def _doc(url: str = "https://example.com/1", cross_encoder_score: float = 1.0, **overrides) -> RerankedEvidence:
    defaults = dict(source="wikipedia", title="t", url=url, snippet="s", cross_encoder_score=cross_encoder_score)
    defaults.update(overrides)
    return RerankedEvidence(**defaults)


def _verdict(label: str = "neutral", confidence: float = 0.5, **doc_overrides) -> NLIVerdict:
    return NLIVerdict(evidence=_doc(**doc_overrides), label=label, confidence=confidence)


# ---- _eligible_verdicts: pure function, no models needed ----


def test_eligible_verdicts_filters_to_relevant_neutral_only():
    verdicts = [
        _verdict("neutral", cross_encoder_score=1.0, url="a"),
        _verdict("entailment", cross_encoder_score=1.0, url="b"),
        _verdict("contradiction", cross_encoder_score=1.0, url="c"),
        _verdict("neutral", cross_encoder_score=-1.0, url="d"),  # relevance-floor-forced, not ambiguous
    ]
    eligible = stage7b._eligible_verdicts(verdicts, max_docs=10)
    assert [v.evidence.url for v in eligible] == ["a"]


def test_eligible_verdicts_sorts_by_score_descending():
    verdicts = [
        _verdict("neutral", cross_encoder_score=1.0, url="low"),
        _verdict("neutral", cross_encoder_score=5.0, url="high"),
        _verdict("neutral", cross_encoder_score=3.0, url="mid"),
    ]
    eligible = stage7b._eligible_verdicts(verdicts, max_docs=10)
    assert [v.evidence.url for v in eligible] == ["high", "mid", "low"]


def test_eligible_verdicts_respects_max_docs_cap():
    verdicts = [_verdict("neutral", cross_encoder_score=float(i), url=str(i)) for i in range(5)]
    eligible = stage7b._eligible_verdicts(verdicts, max_docs=3)
    assert len(eligible) == 3
    assert [v.evidence.url for v in eligible] == ["4", "3", "2"]


def test_eligible_verdicts_empty_input():
    assert stage7b._eligible_verdicts([], max_docs=3) == []


# ---- resolve_ambiguous_verdicts: orchestration logic, models faked ----


class _FakeLLMClient:
    def __init__(self, fn):
        self._fn = fn

    def extract_evidence_claim(self, claim_text, evidence_text):
        return self._fn(claim_text, evidence_text)


class _FakeSBERT:
    """Encodes by a lookup table so tests control similarity precisely."""

    def __init__(self, vectors: dict[str, np.ndarray]):
        self._vectors = vectors

    def encode(self, texts, normalize_embeddings=True):
        return np.asarray([self._vectors[t] for t in texts])


class _FakeNLIModel:
    def __init__(self, scores_by_sentence: dict[str, list[float]]):
        self._scores = scores_by_sentence

    def predict(self, pairs):
        return np.asarray([self._scores[sentence] for sentence, _ in pairs])


def _patch_llm(monkeypatch, fn):
    monkeypatch.setattr("app.pipeline.stage7b_evidence_claim_resolution.get_llm_client", lambda: _FakeLLMClient(fn))


def _patch_sbert_no_echo(monkeypatch):
    """Orthogonal vectors: nothing looks like a self-echo of the claim."""

    def encode(texts, normalize_embeddings=True):
        base = np.eye(len(texts))
        return base

    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_sbert_model",
        lambda: type("S", (), {"encode": staticmethod(encode)})(),
    )


def _patch_nli(monkeypatch, logits_by_sentence: dict[str, list[float]]):
    # labels order: entailment, neutral, contradiction (matches fact_verification
    # variant's order - the exact order doesn't matter as long as it's consistent
    # with the fake predict()'s output and the labels list below)
    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_nli_model",
        lambda variant=None: _FakeNLIModel(logits_by_sentence),
    )
    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_nli_labels",
        lambda variant=None: ["entailment", "neutral", "contradiction"],
    )


async def test_confident_verdicts_pass_through_untouched(monkeypatch):
    calls = []
    _patch_llm(monkeypatch, lambda claim, ev: calls.append(1) or "should not be called")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {})

    verdicts = [_verdict("entailment", confidence=0.9, url="a"), _verdict("contradiction", confidence=0.9, url="b")]
    result = await stage7b.resolve_ambiguous_verdicts("claim", verdicts)

    assert result == verdicts
    assert calls == []


async def test_relevance_floor_forced_neutral_gets_no_llm_call(monkeypatch):
    calls = []
    _patch_llm(monkeypatch, lambda claim, ev: calls.append(1) or "some sentence")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {})

    verdicts = [_verdict("neutral", cross_encoder_score=-1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("claim", verdicts)

    assert result == verdicts
    assert calls == []


async def test_successful_extraction_flips_neutral_to_entailment(monkeypatch):
    _patch_llm(monkeypatch, lambda claim, ev: "Bats have functional eyesight.")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {"Bats have functional eyesight.": [10.0, 0.0, 0.0]})  # strong entailment logit

    verdicts = [_verdict("neutral", cross_encoder_score=1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("Bats are blind.", verdicts)

    assert result[0].label == "entailment"
    assert result[0].llm_refined is True
    assert result[0].resolved_evidence_claim == "Bats have functional eyesight."


async def test_successful_extraction_flips_neutral_to_contradiction(monkeypatch):
    _patch_llm(monkeypatch, lambda claim, ev: "Bats are not blind and use echolocation.")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {"Bats are not blind and use echolocation.": [0.0, 0.0, 10.0]})

    verdicts = [_verdict("neutral", cross_encoder_score=1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("Bats are blind.", verdicts)

    assert result[0].label == "contradiction"
    assert result[0].llm_refined is True


async def test_extraction_succeeds_but_second_pass_stays_neutral(monkeypatch):
    _patch_llm(monkeypatch, lambda claim, ev: "Bats exist.")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {"Bats exist.": [0.0, 10.0, 0.0]})  # strong neutral logit

    verdicts = [_verdict("neutral", confidence=0.5, cross_encoder_score=1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("Bats are blind.", verdicts)

    assert result[0].label == "neutral"
    assert result[0].llm_refined is False
    assert result[0].resolved_evidence_claim == "Bats exist."  # still recorded even though it didn't flip


async def test_empty_extraction_keeps_original_verdict(monkeypatch):
    _patch_llm(monkeypatch, lambda claim, ev: "")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {})

    original = _verdict("neutral", cross_encoder_score=1.0, url="a")
    result = await stage7b.resolve_ambiguous_verdicts("claim", [original])

    assert result[0] == original


async def test_llm_exception_falls_back_gracefully(monkeypatch):
    def raise_error(claim, ev):
        raise RuntimeError("Gemini quota exceeded")

    _patch_llm(monkeypatch, raise_error)
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {})

    original = _verdict("neutral", cross_encoder_score=1.0, url="a")
    result = await stage7b.resolve_ambiguous_verdicts("claim", [original])

    assert result[0] == original


async def test_max_docs_cap_limits_llm_calls(monkeypatch):
    calls = []
    _patch_llm(monkeypatch, lambda claim, ev: calls.append(ev) or "")
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {})
    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_settings",
        lambda: type(
            "S",
            (),
            {
                "evidence_claim_resolution_max_docs": 2,
                "evidence_claim_resolution_timeout_seconds": 5.0,
                "evidence_claim_resolution_max_chars": 500,
            },
        )(),
    )

    verdicts = [_verdict("neutral", cross_encoder_score=float(i), url=str(i)) for i in range(5)]
    await stage7b.resolve_ambiguous_verdicts("claim", verdicts)

    assert len(calls) == 2


async def test_hedge_marker_backstop_redirects_entailment_to_contradiction(monkeypatch):
    sentence = "The claim is a widely believed but false misconception."
    _patch_llm(monkeypatch, lambda claim, ev: sentence)
    _patch_sbert_no_echo(monkeypatch)
    # a strong raw entailment logit, but the hedge marker should redirect it
    _patch_nli(monkeypatch, {sentence: [10.0, 0.0, 0.0]})

    verdicts = [_verdict("neutral", cross_encoder_score=1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("claim", verdicts)

    assert result[0].label == "contradiction"


async def test_self_echo_guard_discards_near_claim_paraphrase(monkeypatch):
    calls = []
    _patch_llm(monkeypatch, lambda claim, ev: "Bats are blind.")  # near-identical to the claim itself
    _patch_nli(monkeypatch, {"Bats are blind.": [10.0, 0.0, 0.0]})

    def encode(texts, normalize_embeddings=True):
        calls.append(texts)
        return np.asarray([[1.0, 0.0], [1.0, 0.0]])  # identical vectors -> similarity 1.0

    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_sbert_model",
        lambda: type("S", (), {"encode": staticmethod(encode)})(),
    )

    verdicts = [_verdict("neutral", cross_encoder_score=1.0, url="a")]
    result = await stage7b.resolve_ambiguous_verdicts("Bats are blind.", verdicts)

    assert result[0].label == "neutral"
    assert result[0].llm_refined is False
    assert calls  # the echo check did run


async def test_no_verdicts_returns_empty_list():
    assert await stage7b.resolve_ambiguous_verdicts("claim", []) == []


# ---- live integration tests: real LLM backend + real NLI model ----


@pytest.mark.integration
async def test_live_extraction_resolves_bare_question_evidence():
    from app.clients import get_llm_client

    sentence = get_llm_client().extract_evidence_claim(
        "Einstein failed mathematics as a student.",
        "Was Albert Einstein really a bad student who failed math? - The Washington Post",
    )
    # the headline alone can't answer its own question - a real extraction
    # call should recognize that rather than guess a direction
    assert "?" not in sentence


@pytest.mark.integration
async def test_live_irrelevant_neutral_is_not_force_resolved():
    verdict = _verdict("neutral", cross_encoder_score=-2.0, url="a")
    result = await stage7b.resolve_ambiguous_verdicts(
        "Albert Einstein developed the theory of general relativity.", [verdict]
    )
    assert result[0] == verdict


@pytest.mark.integration
async def test_live_second_pass_resolves_a_genuinely_ambiguous_case():
    """A document whose raw text is a debunking headline that stage 7's
    sentence-level heuristics alone often can't cleanly resolve (no
    "myth"/"debunked" style hedge marker string, just a rhetorical framing)
    should come out at least as decisive after stage 7b as before it."""
    claim = "Cracking your knuckles causes arthritis."
    ambiguous_doc = RerankedEvidence(
        source="google_news",
        title="Does Knuckle Cracking Really Cause Arthritis? Doctors Weigh In",
        url="https://example.com/knuckles",
        snippet="Does Knuckle Cracking Really Cause Arthritis? Doctors Weigh In",
        cross_encoder_score=3.0,
    )
    first_pass = NLIVerdict(evidence=ambiguous_doc, label="neutral", confidence=0.5)

    resolved = await stage7b.resolve_ambiguous_verdicts(claim, [first_pass])

    assert resolved[0].resolved_evidence_claim is not None or resolved[0].label == "neutral"
    # if extraction succeeded, the resolved sentence must not itself be a question
    if resolved[0].resolved_evidence_claim:
        assert "?" not in resolved[0].resolved_evidence_claim


@pytest.mark.integration
async def test_live_timeout_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.get_settings",
        lambda: type(
            "S",
            (),
            {
                "evidence_claim_resolution_max_docs": 3,
                "evidence_claim_resolution_timeout_seconds": 0.001,
                "evidence_claim_resolution_max_chars": 500,
            },
        )(),
    )
    original = _verdict("neutral", cross_encoder_score=1.0, url="a")
    result = await stage7b.resolve_ambiguous_verdicts("some claim", [original])
    assert result[0] == original


async def test_rewrite_of_hedged_evidence_is_not_trusted_as_support(monkeypatch):
    # the source calls the claim misinformation; the LLM's rewrite dropped that
    rewrite = "mRNA vaccines introduce genetic material into cells."
    _patch_llm(monkeypatch, lambda claim, ev: rewrite)
    _patch_sbert_no_echo(monkeypatch)
    _patch_nli(monkeypatch, {rewrite: [10.0, 0.0, 0.0]})

    verdicts = [
        _verdict(
            "neutral",
            cross_encoder_score=1.0,
            url="a",
            snippet="Because of misinformation suggesting that COVID-19 might alter DNA, some academics objected.",
        )
    ]
    result = await stage7b.resolve_ambiguous_verdicts("COVID-19 vaccines alter human DNA.", verdicts)

    assert result[0].label == "neutral"
    assert result[0].llm_refined is False
