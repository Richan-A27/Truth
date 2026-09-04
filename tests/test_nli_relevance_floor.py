import pytest

from app.pipeline.stage7_nli_verification import verify_claim
from app.schemas.ranking import RerankedEvidence


@pytest.mark.integration
def test_low_relevance_evidence_is_forced_neutral_not_contradiction():
    """cross-encoder/nli-deberta-v3-base is biased toward labeling unrelated
    pairs as 'contradiction'; evidence the reranker scored as irrelevant
    (negative cross_encoder_score) must not be allowed to count as
    supporting or contradicting evidence."""
    irrelevant = RerankedEvidence(
        source="wikipedia",
        title="Government cheese",
        url="https://en.wikipedia.org/wiki/Government_cheese",
        snippet="Government cheese is processed cheese provided to welfare beneficiaries.",
        cross_encoder_score=-9.4,
    )
    verdicts = verify_claim("The moon is made of green cheese.", [irrelevant])
    assert verdicts[0].label == "neutral"


@pytest.mark.integration
def test_relevant_evidence_keeps_its_real_verdict():
    relevant = RerankedEvidence(
        source="wikipedia",
        title="Eiffel Tower",
        url="https://en.wikipedia.org/wiki/Eiffel_Tower",
        snippet="The Eiffel Tower is a lattice tower on the Champ de Mars in Paris, France.",
        cross_encoder_score=5.2,
    )
    verdicts = verify_claim("The Eiffel Tower is located in Berlin, Germany.", [relevant])
    assert verdicts[0].label == "contradiction"
