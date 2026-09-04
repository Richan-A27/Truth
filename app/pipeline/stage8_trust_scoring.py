import math
import re

from app.schemas.claim import Claim
from app.schemas.nli import NLIVerdict
from app.schemas.trust import ClaimTrustResult

SOURCE_RELIABILITY_WEIGHTS = {
    "semantic_scholar": 1.0,
    "gdelt": 0.8,
    "wikipedia": 0.7,
}

LABEL_SIGN = {"entailment": 1.0, "contradiction": -1.0, "neutral": 0.0}

LIKELY_TRUE_THRESHOLD = 70
LIKELY_FALSE_THRESHOLD = 30

# Stops a single confident-but-wrong NLI call from producing a 0/100 verdict:
# with n decisive items the score keeps n/(n+k) of its raw magnitude. Kept
# small deliberately - at k=2.0 this over-shrank real verdicts (a clearly
# false myth landed at 49/"mixed"), so k=0.5 leaves one item at 67% and three
# at 86% while still denying any single item the extremes.
EVIDENCE_SHRINKAGE_CONSTANT = 0.5

# Floor for evidence that shares none of the claim's named entities: it still
# counts a little (the claim may have no usable entities, or the evidence may
# refer to them obliquely) but cannot outvote on-topic evidence. Coverage is
# squared before weighting because a partial match is usually a same-name
# different-subject page ("Eiffel Tower (Paris, Texas)" covers 2 of 3
# entities but is about another continent), not a weaker version of a match.
MIN_ENTITY_COVERAGE_WEIGHT = 0.15

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TRIVIAL_TOKENS = {"the", "a", "an", "of", "in", "on", "at", "and"}


def _entity_coverage(claim: Claim, evidence_text: str) -> float:
    """Fraction of the claim's named entities that the evidence mentions.

    Retrieval happily returns pages about a *different* entity with a similar
    name - "Eiffel Tower (Paris, Texas)" for a claim about the Paris in
    France, or Jupiter's own moons for a claim about Earth's Moon - and the
    NLI model then reports a confident contradiction. Requiring the evidence
    to actually mention what the claim is about separates those distractors
    from genuinely on-topic sources.
    """
    if not claim.entities:
        return 1.0  # no entity signal available; don't penalise anything

    evidence_tokens = set(_TOKEN_RE.findall(evidence_text.lower()))
    covered = 0
    for entity in claim.entities:
        tokens = {t for t in _TOKEN_RE.findall(entity.text.lower()) if t not in _TRIVIAL_TOKENS}
        if tokens and tokens <= evidence_tokens:
            covered += 1
    return covered / len(claim.entities)


def score_claim(claim: Claim, verdicts: list[NLIVerdict]) -> ClaimTrustResult:
    supporting = [v for v in verdicts if v.label == "entailment"]
    contradicting = [v for v in verdicts if v.label == "contradiction"]
    neutral = [v for v in verdicts if v.label == "neutral"]

    if not verdicts:
        return ClaimTrustResult(
            claim=claim,
            trust_score=50,
            verdict_label="unverified",
            supporting_evidence=[],
            contradicting_evidence=[],
            explanation="",
            breakdown={
                "neutral_count": 0,
                "source_reliability_weight": 0.0,
                "confidence_weight": 0.0,
                "reason": "no evidence found",
                "verdict_label": "unverified",
            },
        )

    # The cross-encoder logit saturates a plain sigmoid: scores of 10.4, 9.6
    # and 2.3 all map to ~1.0, throwing away the ranking entirely. Scoring
    # each item relative to the best-ranked one preserves that ordering.
    top_relevance = max(v.evidence.cross_encoder_score for v in verdicts)

    weighted_sum = 0.0
    total_weight = 0.0
    coverage_by_verdict = []
    for v in verdicts:
        source_weight = SOURCE_RELIABILITY_WEIGHTS.get(v.evidence.source, 0.5)
        relevance_weight = 1.0 / (1.0 + math.exp(-(v.evidence.cross_encoder_score - top_relevance)))
        coverage = _entity_coverage(claim, f"{v.evidence.title} {v.evidence.snippet}")
        coverage_weight = MIN_ENTITY_COVERAGE_WEIGHT + (1.0 - MIN_ENTITY_COVERAGE_WEIGHT) * coverage**2
        coverage_by_verdict.append(coverage)

        weight = source_weight * relevance_weight * coverage_weight
        weighted_sum += LABEL_SIGN[v.label] * v.confidence * weight
        total_weight += weight

    avg_source_weight = sum(
        SOURCE_RELIABILITY_WEIGHTS.get(v.evidence.source, 0.5) for v in verdicts
    ) / len(verdicts)
    avg_confidence = sum(v.confidence for v in verdicts) / len(verdicts)

    normalized = weighted_sum / total_weight if total_weight > 0 else 0.0  # in [-1, 1]

    # Shrink toward "uncertain" when the verdict rests on very few decisive
    # evidence items. A single confident-but-wrong NLI call should not be able
    # to produce a 0/100 or 100/100 verdict; certainty has to be earned by
    # several independent sources agreeing.
    decisive_count = len(supporting) + len(contradicting)
    evidence_confidence = decisive_count / (decisive_count + EVIDENCE_SHRINKAGE_CONSTANT)
    normalized *= evidence_confidence

    trust_score = round(50 + normalized * 50)
    trust_score = max(0, min(100, trust_score))

    if decisive_count == 0:
        verdict_label = "unverified"
    elif trust_score >= LIKELY_TRUE_THRESHOLD:
        verdict_label = "likely_true"
    elif trust_score <= LIKELY_FALSE_THRESHOLD:
        verdict_label = "likely_false"
    else:
        verdict_label = "mixed"

    return ClaimTrustResult(
        claim=claim,
        trust_score=trust_score,
        verdict_label=verdict_label,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        explanation="",
        breakdown={
            "neutral_count": len(neutral),
            "source_reliability_weight": avg_source_weight,
            "confidence_weight": avg_confidence,
            "normalized_score": normalized,
            "decisive_evidence_count": decisive_count,
            "evidence_confidence": evidence_confidence,
            "mean_entity_coverage": sum(coverage_by_verdict) / len(coverage_by_verdict),
            "verdict_label": verdict_label,
        },
    )
