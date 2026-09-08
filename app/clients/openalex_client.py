import html
import logging
from datetime import datetime

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.openalex.org/works"

MAX_ABSTRACT_WORDS = 200


def _clean(text: str) -> str:
    return html.unescape(text).strip()


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex withholds plain abstracts for copyright reasons and instead
    returns an inverted index (word -> the positions it occurs at); the
    original text has to be rebuilt from it before it's usable as an NLI
    premise."""
    if not inverted_index:
        return ""
    position_to_word: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_to_word[pos] = word
    if not position_to_word:
        return ""
    ordered = [position_to_word[i] for i in sorted(position_to_word)[:MAX_ABSTRACT_WORDS]]
    return " ".join(ordered)


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    params = {
        "search": query,
        "per-page": limit,
    }
    if settings.openalex_mailto:
        # OpenAlex's "polite pool" - identifying requests with a contact
        # email gets a higher, more stable rate limit than anonymous calls
        params["mailto"] = settings.openalex_mailto

    async with httpx.AsyncClient(timeout=settings.openalex_timeout_seconds) as client:
        resp = await client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        works = resp.json().get("results", [])

    docs = []
    for work in works:
        title = _clean(work.get("title") or work.get("display_name") or "")
        abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
        snippet = _clean(abstract) or title
        if not title or not snippet:
            continue

        url = work.get("doi") or (work.get("primary_location") or {}).get("landing_page_url") or work.get("id") or ""

        published_date = None
        pub_date = work.get("publication_date")
        if pub_date:
            try:
                published_date = datetime.strptime(pub_date, "%Y-%m-%d")
            except ValueError:
                published_date = None

        docs.append(
            EvidenceDocument(
                source="openalex",
                title=title,
                url=url,
                snippet=snippet[:1000],
                published_date=published_date,
            )
        )
    return docs
