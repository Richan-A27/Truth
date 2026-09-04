import html
import logging
import re
from datetime import datetime

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def _clean(text: str) -> str:
    """Abstracts arrive with markup ("<p><strong>Context:</strong></p>") that
    would otherwise end up in the NLI premise."""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    async with httpx.AsyncClient(timeout=settings.semantic_scholar_timeout_seconds, headers=headers) as client:
        resp = await client.get(
            SEARCH_URL,
            params={
                "query": query,
                "limit": limit,
                "fields": "title,abstract,url,year,publicationDate",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    papers = data.get("data", [])
    docs = []
    for item in papers:
        title = _clean(item.get("title") or "")
        abstract = _clean(item.get("abstract") or "") or title
        if not abstract:
            continue
        published_date = None
        pub_date = item.get("publicationDate")
        if pub_date:
            try:
                published_date = datetime.strptime(pub_date, "%Y-%m-%d")
            except ValueError:
                published_date = None
        docs.append(
            EvidenceDocument(
                source="semantic_scholar",
                title=title,
                url=item.get("url") or "",
                snippet=abstract[:1000],
                published_date=published_date,
            )
        )
    return docs
