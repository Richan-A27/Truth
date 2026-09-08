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

SEARCH_URL = "https://api.crossref.org/works"

_DATE_FIELDS = ("published", "published-print", "published-online")


def _clean(text: str) -> str:
    # Abstracts arrive as JATS XML ("<jats:p>...</jats:p>") when present at all
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _extract_date(item: dict) -> datetime | None:
    for field in _DATE_FIELDS:
        parts = (item.get(field) or {}).get("date-parts")
        if not parts or not parts[0]:
            continue
        year_month_day = (parts[0] + [1, 1])[:3]
        try:
            return datetime(*year_month_day)
        except (ValueError, TypeError):
            continue
    return None


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    params = {"query": query, "rows": limit}
    if settings.crossref_mailto:
        # CrossRef's "polite pool" - identified requests get priority over
        # anonymous ones, the same convention OpenAlex and Wikipedia use.
        params["mailto"] = settings.crossref_mailto

    async with httpx.AsyncClient(timeout=settings.crossref_timeout_seconds) as client:
        resp = await client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])

    docs = []
    for item in items:
        title = _clean((item.get("title") or [""])[0])
        if not title:
            continue
        # most CrossRef records (books, many journal articles) carry no
        # abstract at all - the title is still a usable, if thin, premise
        abstract = _clean(item.get("abstract") or "")
        snippet = abstract or title

        docs.append(
            EvidenceDocument(
                source="crossref",
                title=title,
                url=item.get("URL") or "",
                snippet=snippet[:1000],
                published_date=_extract_date(item),
            )
        )
    return docs
