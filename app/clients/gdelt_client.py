import html
import logging
from datetime import datetime

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.gdelt_timeout_seconds) as client:
        resp = await client.get(
            DOC_API_URL,
            params={
                "query": query,
                "mode": "artlist",
                "maxrecords": limit,
                "format": "json",
                "sort": "hybridrel",
            },
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            # GDELT occasionally returns a non-JSON error page with a 200 status
            logger.warning("GDELT returned non-JSON response for query %r", query)
            return []

    articles = data.get("articles", [])
    docs = []
    for item in articles:
        published_date = None
        seendate = item.get("seendate")
        if seendate:
            try:
                published_date = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
            except ValueError:
                published_date = None
        title = html.unescape(item.get("title", "")).strip()
        if not title:
            continue
        docs.append(
            EvidenceDocument(
                source="gdelt",
                title=title,
                url=item.get("url", ""),
                snippet=title,  # GDELT doc API doesn't return full snippets
                published_date=published_date,
            )
        )
    return docs
