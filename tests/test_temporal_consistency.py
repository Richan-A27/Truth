from datetime import datetime

from app.pipeline.stage8_trust_scoring import (
    TEMPORAL_MISMATCH_WEIGHT,
    _extract_claim_year,
    _temporal_consistency,
    score_claim,
)
from app.schemas.claim import Claim, ExtractedEntity
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence


def _claim_with_entities(text: str, entities: list[tuple[str, str]]) -> Claim:
    return Claim(text=text, order=0, entities=[ExtractedEntity(text=t, label=l) for t, l in entities])


def test_extracts_year_from_date_entity():
    claim = _claim_with_entities("x", [("February 2021", "DATE")])
    assert _extract_claim_year(claim) == 2021


def test_no_year_when_no_date_entity():
    claim = _claim_with_entities("x", [("Paris", "GPE")])
    assert _extract_claim_year(claim) is None


def test_no_year_when_date_entity_has_no_digits():
    claim = _claim_with_entities("x", [("last year", "DATE")])
    assert _extract_claim_year(claim) is None


def test_consistency_is_full_when_claim_has_no_year():
    assert _temporal_consistency(None, datetime(1990, 1, 1)) == 1.0


def test_consistency_is_full_when_evidence_has_no_date():
    assert _temporal_consistency(2021, None) == 1.0


def test_consistency_is_full_when_evidence_postdates_claim():
    assert _temporal_consistency(2021, datetime(2024, 1, 1)) == 1.0
    assert _temporal_consistency(2021, datetime(2021, 6, 1)) == 1.0  # same year, not penalised


def test_consistency_is_downweighted_when_evidence_predates_claim():
    """A source cannot report on an event that had not happened yet."""
    assert _temporal_consistency(2021, datetime(2019, 1, 1)) == TEMPORAL_MISMATCH_WEIGHT


def _verdict(label: str, title: str, snippet: str, ce: float, published=None) -> NLIVerdict:
    evidence = RerankedEvidence(
        source="gdelt",
        title=title,
        url=f"https://example.com/{title}",
        snippet=snippet,
        cross_encoder_score=ce,
        published_date=published,
    )
    return NLIVerdict(evidence=evidence, label=label, confidence=0.95)


def test_score_claim_downweights_evidence_that_predates_the_claimed_event():
    """Weighting only shows up in relative terms (a lone item's own weight
    cancels out of the weighted average), so this pits a temporally-plausible
    supporting item against an implausible contradicting one: without
    temporal weighting they'd roughly cancel out at 50/mixed, but the
    implausible item (dated before the event it supposedly reports on)
    should be discounted enough to let the plausible one win."""
    claim = _claim_with_entities(
        "A new species was discovered in the Amazon in 2023.",
        [("2023", "DATE")],
    )
    verdicts = [
        _verdict("entailment", "New article", "some new text", 8.0, published=datetime(2023, 6, 1)),
        _verdict("contradiction", "Old article", "some old text", 8.0, published=datetime(2015, 1, 1)),
    ]

    result = score_claim(claim, verdicts)

    assert result.trust_score >= 70, f"expected the plausible evidence to dominate, got {result.trust_score}"
