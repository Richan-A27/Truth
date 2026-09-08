import pytest


@pytest.mark.integration
async def test_live_resolve_returns_disambiguating_description():
    from app.clients.wikidata_client import resolve_description

    description = await resolve_description("Paris")
    assert description is not None
    assert "france" in description.lower()


@pytest.mark.integration
async def test_live_resolve_returns_none_for_nonsense():
    from app.clients.wikidata_client import resolve_description

    description = await resolve_description("zzqxnotarealthing12345")
    assert description is None
