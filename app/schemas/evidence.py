from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EvidenceDocument(BaseModel):
    source: Literal["gdelt", "semantic_scholar", "wikipedia"]
    title: str
    url: str
    snippet: str
    published_date: datetime | None = None


class RetrievedEvidence(EvidenceDocument):
    bm25_score: float = 0.0
