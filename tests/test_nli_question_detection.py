import pytest

from app.pipeline.stage7_nli_verification import _is_unanswered_question, verify_claim
from app.schemas.ranking import RerankedEvidence


def test_detects_question_headline():
    assert _is_unanswered_question("Was Albert Einstein really a bad student who failed math?") is True


def test_plain_factual_sentence_is_not_a_question():
    assert _is_unanswered_question("Albert Einstein failed mathematics as a student.") is False


def test_question_with_trailing_whitespace_still_detected():
    assert _is_unanswered_question("Is the Earth flat?  ") is True


def test_question_with_trailing_source_suffix_still_detected():
    # spaCy's sentencizer keeps a headline's "- Source Name" suffix attached
    # to the question span, stranding the "?" mid-sentence rather than at
    # the end - this is the exact shape Google News headlines take.
    assert _is_unanswered_question("Was Albert Einstein really a bad student who failed math? -") is True


@pytest.mark.integration
def test_question_headline_does_not_score_as_confident_entailment():
    """The real Google News headline, verbatim: scored 0.97 entailment
    against "Einstein failed mathematics as a student" before this fix,
    dragging three confident Wikipedia contradictions down to "mixed" - the
    linked Washington Post article debunks the claim, but the headline
    alone (all Google News gives us, no article body) can't say so."""
    evidence = RerankedEvidence(
        source="google_news",
        title="Was Albert Einstein really a bad student who failed math? - The Washington Post",
        url="https://example.com/einstein-math",
        snippet="Was Albert Einstein really a bad student who failed math? - The Washington Post",
        cross_encoder_score=7.49,
    )
    verdicts = verify_claim("Albert Einstein failed mathematics as a student.", [evidence])
    assert verdicts[0].label == "neutral"
