import pytest

from app.pipeline.stage7_nli_verification import _with_preceding_context, verify_claim
from app.schemas.ranking import RerankedEvidence


def test_first_sentence_has_no_predecessor():
    sentences = ["Only sentence."]
    assert _with_preceding_context(sentences, 0) == "Only sentence."


def test_prepends_the_immediately_preceding_sentence():
    sentences = ["First sentence.", "Second sentence.", "Third sentence."]
    assert _with_preceding_context(sentences, 1) == "First sentence. Second sentence."
    assert _with_preceding_context(sentences, 2) == "Second sentence. Third sentence."


@pytest.mark.integration
def test_anaphoric_reference_no_longer_scores_as_confident_entailment():
    """Regression test: the real Wikipedia "5G" article, verbatim. In
    isolation, "The first claims that radiation from 5G weakens the immune
    system..." reads as a confident, unhedged assertion and scored
    entailment at 1.00 against a claim that 5G weakens the immune system -
    a real, live misfire caught via scripts/trace_pipeline.py. The sentence
    is only unambiguous with its predecessor ("Two main versions of the
    conspiracy theory exist:") restored, which is exactly what
    _with_preceding_context does."""
    evidence = RerankedEvidence(
        source="wikipedia",
        title="5G",
        url="https://en.wikipedia.org/wiki/5G",
        snippet=(
            "Two main versions of the conspiracy theory exist: The first claims that radiation from 5G "
            "weakens the immune system, making people more vulnerable to SARS-CoV-2, the virus that causes "
            "COVID-19. The second claims that 5G causes COVID-19."
        ),
        cross_encoder_score=6.8,
    )
    verdicts = verify_claim("Exposure to 5G signals is said to weaken the immune system", [evidence])
    assert verdicts[0].label != "entailment"
