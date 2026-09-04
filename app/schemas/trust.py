from pydantic import BaseModel

from app.schemas.claim import Claim
from app.schemas.nli import NLIVerdict


class ClaimTrustResult(BaseModel):
    claim: Claim
    trust_score: int  # 0-100
    verdict_label: str
    supporting_evidence: list[NLIVerdict]
    contradicting_evidence: list[NLIVerdict]
    explanation: str
    breakdown: dict
