from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    text: str
    label: str  # PERSON, ORG, GPE, DATE, ...


class Claim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    order: int
    entities: list[ExtractedEntity] = Field(default_factory=list)
