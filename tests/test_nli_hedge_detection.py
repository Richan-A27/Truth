import pytest

from app.pipeline.stage7_nli_verification import _is_hedged, verify_claim
from app.schemas.ranking import RerankedEvidence


def test_detects_myth_marker():
    assert _is_hedged("This is commonly regarded as a myth.") is True


def test_detects_fanciful_belief_marker():
    assert _is_hedged('"The Moon is made of green cheese" is a fanciful belief.') is True


def test_detects_debunked_marker():
    assert _is_hedged("The claim has been thoroughly debunked by scientists.") is True


def test_plain_factual_sentence_is_not_hedged():
    assert _is_hedged("Paris is the capital of France.") is False


@pytest.mark.integration
def test_myth_description_is_scored_as_contradiction_not_entailment():
    evidence = RerankedEvidence(
        source="wikipedia",
        title="The Moon is made of green cheese",
        url="https://en.wikipedia.org/wiki/The_Moon_is_made_of_green_cheese",
        snippet='"The Moon is made of green cheese" is a statement referring to a fanciful belief '
        "that the Moon is composed of cheese.",
        cross_encoder_score=9.8,
    )
    verdicts = verify_claim("The moon is made of green cheese.", [evidence])
    assert verdicts[0].label == "contradiction"


@pytest.mark.integration
@pytest.mark.xfail(
    reason=(
        "Known, unresolved model limitation - see stage7_nli_verification.py's "
        "module docstring note on 'specific-detail mismatch'. Kept as a live "
        "regression probe rather than deleted, so a future model swap or fix "
        "is visible the moment this starts passing."
    ),
    strict=False,
)
def test_specific_detail_mismatch_is_not_scored_as_contradiction():
    """The real Wikipedia 'Albert Einstein' extract, verbatim, scored this
    true claim 10/100 "likely_false". It is NOT a hedge-marker bug (this text
    contains none) and NOT fixed by restricting NLI to the most
    claim-relevant sentences (see TOP_SENTENCES_FOR_NLI): the sentence
    mentioning "special relativity" and the one mentioning "quantum theory"
    are both topically relevant (0.50 and 0.65 SBERT similarity to the
    claim, not noise) and each independently scores >99% contradiction
    against a claim naming "general relativity" specifically. The model
    appears to treat "mentions a different specific detail" as refutation
    rather than as an unaddressed aspect - a deeper calibration issue than
    anything sentence selection or hedge detection can route around.
    """
    evidence = RerankedEvidence(
        source="wikipedia",
        title="Albert Einstein",
        url="https://en.wikipedia.org/wiki/Albert_Einstein",
        snippet=(
            "Albert Einstein (14 March 1879 – 18 April 1955) was a German-born theoretical "
            "physicist best known for developing the theory of relativity. Einstein also made "
            "important contributions to quantum theory. His mass–energy equivalence formula "
            'E = mc2, which arises from special relativity, has been called "the world\'s most '
            'famous equation". He received the 1921 Nobel Prize in Physics for "his services to '
            'theoretical physics, and especially for his discovery of the law of the '
            'photoelectric effect". Born as a subject to the Kingdom of Württemberg, part of '
            "the German Empire, Einstein moved to Switzerland in 1895, forsaking his citizenship "
            "the following year."
        ),
        cross_encoder_score=7.99,
    )
    verdicts = verify_claim("Albert Einstein developed the theory of general relativity.", [evidence])
    assert verdicts[0].label == "entailment"


def test_no_evidence_phrasing_counts_as_hedge():
    assert _is_hedged("There is no evidence that COVID-19 vaccination causes cancer.") is True
    assert _is_hedged("The idea is not supported by cancer research.") is True
