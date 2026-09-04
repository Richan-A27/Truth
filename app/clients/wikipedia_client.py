import html
import logging
import re

import httpx

from app.config import get_settings
from app.core.resilience import retry_external_call
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "TruthVerificationBot/0.1 (educational project)"}

MAX_EXTRACT_CHARS = 1200


@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.wikipedia_timeout_seconds, headers=HEADERS) as client:
        resp = await client.get(
            API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])

        titles = [item["title"] for item in results if item.get("title")]
        extracts = await _fetch_intro_extracts(client, titles) if titles else {}

    docs = []
    for item in results:
        title = item.get("title", "")
        # disambiguation pages just list other articles - they assert nothing,
        # but "The flat Earth is the idea that the Earth is flat." reads as a
        # confident entailment to an NLI model
        if "(disambiguation)" in title.lower():
            continue
        # the intro extract is clean prose; the search snippet is a keyword-
        # highlighted fragment that is usually cut off mid-sentence, so it is
        # only a fallback
        text = extracts.get(title) or _clean(item.get("snippet", ""))
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


async def _fetch_intro_extracts(client: httpx.AsyncClient, titles: list[str]) -> dict[str, str]:
    """Fetch the lead section of each page as plain text, in one batched call."""
    try:
        resp = await client.get(
            API_URL,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "titles": "|".join(titles),
                "format": "json",
            },
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Wikipedia extract fetch failed, falling back to snippets: %s", exc)
        return {}

    extracts = {}
    for page in pages.values():
        title, extract = page.get("title"), page.get("extract")
        if title and extract:
            extracts[title] = _clean(extract)[:MAX_EXTRACT_CHARS]
    return extracts


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
