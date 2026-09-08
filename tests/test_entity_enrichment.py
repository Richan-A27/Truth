from app.pipeline.stage3_evidence_search import enrich_entities_with_wikidata
from app.schemas.claim import ExtractedEntity


async def test_enriches_queryable_entities(monkeypatch):
    async def fake_resolve(text):
        return {"Paris": "capital and most populous city in France"}.get(text)

    monkeypatch.setattr("app.clients.wikidata_client.resolve_description", fake_resolve)

    entities = [ExtractedEntity(text="Paris", label="GPE"), ExtractedEntity(text="1889", label="DATE")]
    enriched = await enrich_entities_with_wikidata(entities)

    by_text = {e.text: e for e in enriched}
    assert by_text["Paris"].wikidata_description == "capital and most populous city in France"
    assert by_text["1889"].wikidata_description is None  # DATE isn't queryable, left untouched


async def test_failed_lookup_leaves_entity_without_description(monkeypatch):
    async def failing_resolve(text):
        raise TimeoutError("wikidata down")

    monkeypatch.setattr("app.clients.wikidata_client.resolve_description", failing_resolve)

    entities = [ExtractedEntity(text="Paris", label="GPE")]
    enriched = await enrich_entities_with_wikidata(entities)

    assert enriched[0].wikidata_description is None


async def test_no_queryable_entities_returns_input_unchanged():
    entities = [ExtractedEntity(text="1889", label="DATE")]
    enriched = await enrich_entities_with_wikidata(entities)
    assert enriched == entities
