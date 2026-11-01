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


def test_subject_query_for_entityless_claims():
    from app.pipeline.stage3_evidence_search import build_subject_query

    assert build_subject_query("The speed of light is approximately 300,000 kilometers per second.") == "speed of light"
    assert build_subject_query("China's First Emperor was buried with an army.") == "China's First Emperor"
    assert build_subject_query("It rained all week.") == ""
