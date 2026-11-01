from app.clients import get_llm_client
from app.schemas.trust import ClaimTrustResult

VERDICT_PHRASING = {
    "likely_true": "is supported by the evidence found",
    "likely_false": "is contradicted by the evidence found",
    "mixed": "has conflicting or inconclusive evidence",
}


def generate_explanation(result: ClaimTrustResult) -> str:
    top_evidence = (result.supporting_evidence + result.contradicting_evidence)[:5]
    snippets = [f"[{v.label}] {v.evidence.title}: {v.evidence.snippet[:200]}" for v in top_evidence]

    return get_llm_client().generate_explanation(
        claim_text=result.claim.text,
        verdict_label=result.verdict_label,
        trust_score=result.trust_score,
        supporting_count=len(result.supporting_evidence),
        contradicting_count=len(result.contradicting_evidence),
        evidence_snippets=snippets,
    )


def build_deterministic_explanation(result: ClaimTrustResult) -> str:
    """Explanation built from the pipeline's own outputs, with no LLM call.

    Used when LLM narration is disabled or unavailable. Because every number
    here comes from the scoring stage rather than a generative model, this
    text cannot hallucinate - which also makes it the honest default for
    reporting how a verdict was reached.
    """
    supporting = result.supporting_evidence
    contradicting = result.contradicting_evidence
    neutral_count = result.breakdown.get("neutral_count", 0)

    if result.verdict_label == "likely_false" and not contradicting:
        # Reached via absence of support rather than an actual contradiction
        # (see stage8_trust_scoring.NO_SUPPORT_SCORE) - phrase it as such.
        phrasing = "could not be backed up by any supporting evidence"
    else:
        phrasing = VERDICT_PHRASING.get(result.verdict_label, "was evaluated")
    parts = [
        f'The claim "{result.claim.text}" scored {result.trust_score}/100 and {phrasing}.',
        f"{len(supporting)} supporting, {len(contradicting)} contradicting and "
        f"{neutral_count} unrelated evidence item(s) were considered.",
    ]

    def _cite(verdicts, label):
        top = sorted(verdicts, key=lambda v: v.evidence.cross_encoder_score, reverse=True)[:2]
        if not top:
            return None
        cited = "; ".join(f"{v.evidence.title} ({v.evidence.source})" for v in top)
        return f"Strongest {label} evidence: {cited}."

    for line in (_cite(supporting, "supporting"), _cite(contradicting, "contradicting")):
        if line:
            parts.append(line)

    if not supporting and not contradicting:
        parts.append(
            "No evidence was found to support the claim, which counts against it."
            if neutral_count == 0
            else "The evidence found didn't address the claim directly, so no support for it was confirmed."
        )

    return " ".join(parts)
