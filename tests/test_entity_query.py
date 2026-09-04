from app.pipeline.stage3_evidence_search import build_entity_query
from app.schemas.claim import ExtractedEntity


def _entities(*pairs) -> list[ExtractedEntity]:
    return [ExtractedEntity(text=t, label=l) for t, l in pairs]


def test_builds_focused_query_from_entities():
    query = build_entity_query(_entities(("William Shakespeare", "PERSON"), ("Hamlet", "WORK_OF_ART")))
    assert query == "William Shakespeare Hamlet"


def test_skips_dates_and_numbers():
    query = build_entity_query(_entities(("NASA", "ORG"), ("February 2021", "DATE"), ("206", "CARDINAL")))
    assert query == "NASA"


def test_deduplicates_repeated_entities():
    query = build_entity_query(_entities(("Paris", "GPE"), ("paris", "GPE"), ("France", "GPE")))
    assert query == "Paris France"


def test_returns_empty_string_without_usable_entities():
    assert build_entity_query([]) == ""
    assert build_entity_query(_entities(("1873", "DATE"))) == ""
