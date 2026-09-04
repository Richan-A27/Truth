import html
import logging
import re

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "TruthVerificationBot/0.1 (educational project)"}

MAX_EXTRACT_CHARS = 1200


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.wikipedia_timeout_seconds, headers=HEADERS) as client:
        # generator=search runs the search and pulls each hit's lead section in
        # a single round trip; fetching extracts separately doubled latency.
        # The lead section is clean prose, unlike the keyword-highlighted
        # search snippet, which arrives truncated mid-sentence.
        resp = await client.get(
            API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "format": "json",
            },
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})

    docs = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        title = page.get("title", "")
        # disambiguation pages just list other articles - they assert nothing,
        # but "The flat Earth is the idea that the Earth is flat." reads as a
        # confident entailment to an NLI model
        if not title or "(disambiguation)" in title.lower():
            continue
        text = _clean(page.get("extract") or "")[:MAX_EXTRACT_CHARS]
        if not text:
            continue
        docs.append(
            EvidenceDocument(
                source="wikipedia",
                title=title,
                url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                snippet=text,
            )
        )
    return docs


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
