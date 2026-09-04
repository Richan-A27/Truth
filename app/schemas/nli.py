from typing import Literal

from pydantic import BaseModel

from app.schemas.ranking import RerankedEvidence


class NLIVerdict(BaseModel):
    evidence: RerankedEvidence
    label: Literal["entailment", "contradiction", "neutral"]
    confidence: float
