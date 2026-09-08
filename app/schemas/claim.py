from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    text: str
    label: str  # PERSON, ORG, GPE, DATE, ...
    # Short disambiguating description from Wikidata (e.g. "capital and
    # largest city of France" for Paris), when resolved - distinguishes
    # evidence about this entity from evidence about a different one that
    # happens to share the same name.
    wikidata_description: str | None = None


class Claim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    order: int
    entities: list[ExtractedEntity] = Field(default_factory=list)
