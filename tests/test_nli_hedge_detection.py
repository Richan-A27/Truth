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
