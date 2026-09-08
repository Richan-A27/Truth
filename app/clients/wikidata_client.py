import logging

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call

logger = logging.getLogger(__name__)

API_URL = "https://www.wikidata.org/w/api.php"


def _headers() -> dict[str, str]:
    # Wikidata runs on the same Wikimedia infrastructure as Wikipedia and
    # returns a bare 403 to requests with no identifying User-Agent.
    contact = get_settings().wikipedia_contact
    identity = f"educational project; {contact}" if contact else "educational project"
    return {"User-Agent": f"TruthVerificationBot/0.1 ({identity})"}

# Entity descriptions are essentially static (a city's description doesn't
# change day to day the way search results do), so these are worth caching
# far longer than the 15-minute default used for evidence lookups.
DESCRIPTION_CACHE_TTL_SECONDS = 24 * 60 * 60


@ttl_cache(ttl_seconds=DESCRIPTION_CACHE_TTL_SECONDS)
@retry_external_call()
async def resolve_description(entity_text: str) -> str | None:
    """The Wikidata description of the best match for an entity's surface
    text, e.g. "Paris" -> "capital and most populous city in France".

    Used to disambiguate same-name entities that plain text search cannot
    tell apart - "Eiffel Tower" alone doesn't distinguish the real one from
    "Eiffel Tower (Paris, Texas)"; their Wikidata descriptions do.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.wikidata_timeout_seconds, headers=_headers()) as client:
        resp = await client.get(
            API_URL,
            params={
                "action": "wbsearchentities",
                "search": entity_text,
                "language": "en",
                "format": "json",
                "limit": 1,
            },
        )
        resp.raise_for_status()
        results = resp.json().get("search", [])

    if not results:
        return None
    return results[0].get("description") or None
