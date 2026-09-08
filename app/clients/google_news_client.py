import html
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

# Unofficial: Google publishes no documented API or stability guarantee for
# this RSS feed (GDELT's replacement, see stage3_evidence_search.py) - it
# could change format or disappear without notice. Used anyway because it
# needs no API key and has shown no rate-limiting in testing, unlike GDELT
# (frequently unreachable) and Semantic Scholar (frequently 429s).
FEED_URL = "https://news.google.com/rss/search"


def _headers() -> dict[str, str]:
    contact = get_settings().wikipedia_contact
    identity = f"educational project; {contact}" if contact else "educational project"
    return {"User-Agent": f"TruthVerificationBot/0.1 ({identity})"}


def _parse_pub_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.google_news_timeout_seconds, headers=_headers()) as client:
        resp = await client.get(
            FEED_URL,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        )
        resp.raise_for_status()

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        logger.warning("Google News returned unparseable XML for query %r", query)
        return []

    docs = []
    for item in root.findall("./channel/item")[:limit]:
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        docs.append(
            EvidenceDocument(
                source="google_news",
                title=title,
                url=link,
                snippet=title,  # the feed carries no article body, only the headline
                published_date=_parse_pub_date(item.findtext("pubDate")),
            )
        )
    return docs
