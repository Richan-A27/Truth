from app.pipeline.stage8_trust_scoring import score_claim
from app.schemas.claim import Claim
from app.schemas.evidence import EvidenceDocument
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence


def _verdict(label: str, confidence: float, source: str = "wikipedia", cross_encoder_score: float = 2.0):
    evidence = RerankedEvidence(
        source=source,
        title="t",
        url=f"https://example.com/{label}-{confidence}",
        snippet="s",
        cross_encoder_score=cross_encoder_score,
    )
    return NLIVerdict(evidence=evidence, label=label, confidence=confidence)


def test_no_evidence_returns_unverified():
    claim = Claim(text="some claim", order=0)
    result = score_claim(claim, [])
    assert result.verdict_label == "unverified"
    assert result.trust_score == 50


def test_all_entailment_scores_high():
    claim = Claim(text="some claim", order=0)
    verdicts = [_verdict("entailment", 0.9) for _ in range(3)]
    result = score_claim(claim, verdicts)
    assert result.trust_score > 50
    assert result.verdict_label == "likely_true"


def test_all_contradiction_scores_low():
    claim = Claim(text="some claim", order=0)
    verdicts = [_verdict("contradiction", 0.9) for _ in range(3)]
    result = score_claim(claim, verdicts)
    assert result.trust_score < 50
    assert result.verdict_label == "likely_false"


def test_more_supporting_evidence_increases_score():
    claim = Claim(text="some claim", order=0)
    fewer = score_claim(claim, [_verdict("entailment", 0.9)])
    more = score_claim(
        claim, [_verdict("entailment", 0.9), _verdict("entailment", 0.9), _verdict("entailment", 0.9)]
    )
    # both should be confidently high; explicitly check monotonic non-decrease
    assert more.trust_score >= fewer.trust_score


def test_mixed_evidence_produces_non_empty_explanation_field_placeholder():
    claim = Claim(text="some claim", order=0)
    verdicts = [_verdict("entailment", 0.6), _verdict("contradiction", 0.6)]
    result = score_claim(claim, verdicts)
    # explanation is filled in by stage9, not stage8 - just assert the breakdown is populated
    assert "verdict_label" in result.breakdown
