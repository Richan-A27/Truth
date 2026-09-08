from typing import Literal

from pydantic import BaseModel

from app.schemas.ranking import RerankedEvidence


class NLIVerdict(BaseModel):
    evidence: RerankedEvidence
    label: Literal["entailment", "contradiction", "neutral"]
    confidence: float
    # Set by stage 7b (app.pipeline.stage7b_evidence_claim_resolution)
    # whenever it successfully extracted a clean sentence for this
    # document, regardless of whether that sentence's second-pass NLI
    # check actually changed the label - useful for eval/debugging either
    # way. None when stage 7b never ran on this verdict (confident
    # first-pass label, or relevance-floor-forced neutral) or extraction
    # failed/timed out.
    resolved_evidence_claim: str | None = None
    # True only when resolved_evidence_claim's second-pass NLI check
    # actually replaced the original first-pass "neutral" label.
    llm_refined: bool = False
