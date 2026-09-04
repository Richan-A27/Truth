from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.trust import ClaimTrustResult


class VerificationRequest(BaseModel):
    content: str
    source_url: str | None = None


class ClaimVerificationRequest(BaseModel):
    claim: str
    source_url: str | None = None
    use_llm_explanation: bool = False


class VerificationResponse(BaseModel):
    run_id: UUID
    trust_score: int
    verdict_label: str
    explanation: str
    claims: list[ClaimTrustResult]
    created_at: datetime
