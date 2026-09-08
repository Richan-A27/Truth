import asyncio
import html
import logging
import re

import httpx

from app.config import get_settings
from app.core.cache import ttl_cache
from app.core.resilience import retry_external_call
from app.core.tokenize import stem_tokenize
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"


def _headers() -> dict[str, str]:
    # Wikimedia's API etiquette ties rate limits to how well a client
    # identifies itself: an unidentified user agent gets throttled harder
    # than one with real contact info. A burst of 22 claims (2 Wikipedia
    # calls each, back-to-back) was enough to trip 429s across the whole run
    # with a generic string.
    contact = get_settings().wikipedia_contact
    identity = f"educational project; {contact}" if contact else "educational project"
    return {"User-Agent": f"TruthVerificationBot/0.1 ({identity})"}


INTRO_CHARS = 500

# A search-match snippet ("...) all of which use laryngeal echolocation),
# a conclusion supported...") is naturally short and often a sentence
# fragment - it exists to point at *where* the match is, not to read well on
# its own. It's still a free, zero-extra-latency relevance signal from
# Wikipedia's own search index, so it's kept alongside the deep-fetch content
# below rather than replaced by it.
MAX_SNIPPET_CHARS = 300

# How many of the ranked search results are worth a second, full-article
# fetch. Bounded low because each one is its own extra HTTP round trip
# (~1-1.5s, run concurrently) - deep-fetching all `limit` results would just
# add latency for candidates that are already unlikely to be cited.
DEEP_FETCH_CANDIDATES = 3

# Wikipedia's `exchars`/`exintro` extract is capped at ~1200 characters
# server-side no matter what's requested (measured directly: exchars=6000
# still returned 1210) - there is no API parameter that returns "a bit more
# of the intro". The only way to reach content stated deeper in an article
# (e.g. the "Bat" article's ~1200-char lead never mentions echolocation or
# vision, which live ~6000+ characters in) is to fetch the full plaintext
# extract and pick the relevant part ourselves.
MAX_DEEP_CONTENT_CHARS = 1200

# Own timeout for the full-article fetch, separate from wikipedia_timeout_seconds
# (which bounds the cheap search+intro call). A slow or failed deep fetch
# degrades to intro+snippet for that one document rather than losing it - but
# that degraded (and possibly wrong) result then gets cached for
# ttl_cache's full window, so it's worth real margin over the ~1.1-1.5s
# measured typical fetch time rather than cutting it close: a claim about
# the Great Wall's visibility from space flipped from a correct likely_false
# to a confidently wrong likely_true across otherwise-identical eval runs,
# traced to this timeout being tight enough for ordinary network jitter to
# occasionally cut off the one article section that debunks the myth.
DEEP_FETCH_TIMEOUT_SECONDS = 3.0

_BOILERPLATE_SECTIONS = {
    "references", "see also", "external links", "further reading", "notes",
    "notes and references", "bibliography", "sources", "gallery", "citations",
    "works cited",
}

# Common words excluded when judging whether the intro+snippet already
# covers a query's *distinctive* vocabulary - without this, function words
# ("the", "of", "is"...) that appear in nearly any sentence pair inflate the
# overlap score enough to erase the gap between "already covers it" and
# "missing the specific fact" (measured: with stopwords included, Einstein's
# intro and Bat's intro scored nearly the same overlap fraction despite one
# already stating the claim and the other omitting it entirely).
_STOPWORDS = {
    "the", "of", "is", "with", "from", "are", "a", "an", "in", "on", "at",
    "to", "and", "or", "but", "was", "were", "be", "been", "being", "it",
    "its", "this", "that", "these", "those", "as", "by", "for",
}

# A candidate whose shallow intro+snippet already contains most of the
# query's distinctive vocabulary doesn't need a deep fetch - reaching for
# more in that case only risks pulling in a sibling-topic passage the NLI
# stage can misread as contradicting a more specific claim. Confirmed on
# "Albert Einstein developed the theory of general relativity": the "Albert
# Einstein" article's intro alone already covers the claim (0.83 overlap),
# but its deep-fetched content included a passage about E=mc2 arising from
# *special* relativity, which the NLI model scored as contradicting the
# general-relativity claim at 0.97 confidence - one spurious contradiction
# was enough to drag three clean entailments down to "mixed" (67). Bats,
# Shakespeare/Hamlet, and the Great Wall myth all measured well below this
# threshold (0.33-0.60) and still need the deep fetch to find their fact.
SHALLOW_RELEVANCE_THRESHOLD = 0.7


def _content_tokens(text: str) -> set[str]:
    return set(stem_tokenize(text)) - _STOPWORDS


def _shallow_relevance(text: str, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 1.0  # nothing distinctive to look for - no reason to reach further
    return len(query_tokens & _content_tokens(text)) / len(query_tokens)


@ttl_cache()
@retry_external_call()
async def search(query: str, limit: int = 5) -> list[EvidenceDocument]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.wikipedia_timeout_seconds, headers=_headers()) as client:
        # generator=search + prop=extracts gets each hit's clean lead section
        # in one round trip. gsrprop=snippet rides along on the *same* call:
        # Wikipedia's full-text search index covers the whole article, not
        # just the lead, so its snippet can point at a fact anywhere in the
        # page.
        resp = await client.get(
            API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "gsrprop": "snippet",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "format": "json",
            },
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})

    candidates = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        title = page.get("title", "")
        # disambiguation pages just list other articles - they assert nothing,
        # but "The flat Earth is the idea that the Earth is flat." reads as a
        # confident entailment to an NLI model
        if title and "(disambiguation)" not in title.lower():
            candidates.append(page)

    query_tokens = _content_tokens(query)

    # Only reach for a full-article fetch when the cheap intro+snippet
    # doesn't already cover the claim's distinctive vocabulary - see
    # SHALLOW_RELEVANCE_THRESHOLD for why a candidate that already looks
    # sufficient shouldn't get one anyway.
    needs_deep_fetch = []
    for page in candidates[:DEEP_FETCH_CANDIDATES]:
        shallow_text = f"{page.get('extract') or ''} {page.get('snippet') or ''}"
        if _shallow_relevance(shallow_text, query_tokens) < SHALLOW_RELEVANCE_THRESHOLD:
            needs_deep_fetch.append(page["title"])

    deep_content = await _fetch_deep_content(needs_deep_fetch, query_tokens)

    docs = []
    for page in candidates:
        title = page["title"]
        intro = _clean(page.get("extract") or "")[:INTRO_CHARS]
        match_snippet = _clean(page.get("snippet") or "")[:MAX_SNIPPET_CHARS]
        deep = deep_content.get(title, "")
        # "\n\n" between parts (and preserved within `deep`, see
        # _fetch_and_score_one) so stage 6's paragraph-level reranking can
        # split back out and score the intro, each deep-fetched paragraph,
        # and the search-match snippet independently, instead of scoring
        # one long blob whose average obscures whichever single part
        # actually answers the claim.
        text = "\n\n".join(part for part in (intro, deep, match_snippet) if part)
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


async def _fetch_deep_content(titles: list[str], query_tokens: set[str]) -> dict[str, str]:
    """Full article text for the top candidates, reduced to the paragraphs
    that actually share vocabulary with the query - the reranker and NLI
    stages downstream truncate to a few hundred tokens anyway, so handing
    them a whole 50KB article would just push the relevant sentence out of
    the window they read."""
    if not query_tokens or not titles:
        return {}

    scored = await asyncio.gather(*(_fetch_and_score_one(title, query_tokens) for title in titles))
    return {title: text for title, text in zip(titles, scored) if text}


async def _fetch_and_score_one(title: str, query_tokens: set[str]) -> str:
    try:
        async with httpx.AsyncClient(timeout=DEEP_FETCH_TIMEOUT_SECONDS, headers=_headers()) as client:
            resp = await client.get(
                API_URL,
                params={"action": "query", "titles": title, "prop": "extracts", "explaintext": 1, "format": "json"},
            )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        full_text = next(iter(pages.values()), {}).get("extract", "")
    except Exception as exc:  # noqa: BLE001 - deep content is a bonus; intro+snippet still stands without it
        logger.warning("Deep-content fetch failed for %r: %s", title, exc)
        return ""

    paragraphs = _paragraphs_excluding_boilerplate(full_text)
    selected = _select_relevant_paragraphs(paragraphs, query_tokens, MAX_DEEP_CONTENT_CHARS)
    # Each paragraph cleaned individually, then rejoined with "\n\n" -
    # cleaning the already-joined blob instead would collapse the
    # separators along with the rest of the whitespace, losing the
    # boundaries stage 6's paragraph-level reranking depends on.
    return "\n\n".join(_clean(p) for p in selected)


def _paragraphs_excluding_boilerplate(full_text: str) -> list[str]:
    # explaintext renders "== Section ==" headers as their own plain-text
    # line, and each paragraph as one line with no internal newline -
    # verified directly against a real article before relying on it.
    paragraphs = []
    in_boilerplate_section = False
    for line in full_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("==") and stripped.endswith("=="):
            in_boilerplate_section = stripped.strip("= ").lower() in _BOILERPLATE_SECTIONS
            continue
        if not in_boilerplate_section:
            paragraphs.append(stripped)
    return paragraphs


def _select_relevant_paragraphs(paragraphs: list[str], query_tokens: set[str], max_chars: int) -> list[str]:
    scored = []
    for i, para in enumerate(paragraphs):
        overlap = len(query_tokens & set(stem_tokenize(para)))
        if overlap > 0:
            scored.append((overlap, i))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    selected: list[str] = []
    seen_indices: set[int] = set()
    total = 0
    for _, i in scored:
        if total >= max_chars:
            break
        if i in seen_indices:
            continue
        text = paragraphs[i]
        seen_indices.add(i)
        # A short "framing" sentence ending in a colon right before a
        # selected paragraph ("Two main versions of the conspiracy theory
        # exist:") often supplies context an anaphoric reference in the
        # selected paragraph depends on, even though it shares no query
        # vocabulary of its own and would otherwise never be picked on its
        # own. Confirmed live: without it, "The first claims that
        # radiation from 5G weakens the immune system..." reads as a
        # confident, unhedged assertion rather than a conspiracy theory
        # being described. Scoped to colon-ending predecessors specifically
        # (not every predecessor) so an unrelated, merely-adjacent
        # paragraph doesn't get pulled in and dilute the selection.
        #
        # Merged into the SAME string rather than appended as its own
        # separate paragraph: the caller rejoins the returned list with
        # "\n\n", and stage 6's paragraph-level reranking treats each
        # "\n\n"-separated chunk as independently scoreable, keeping only
        # the single best one - two separate entries here would let stage 6
        # split this exact pairing straight back apart and lose the
        # context one stage later, which is what happened before this was
        # merged into one chunk instead of two.
        if i > 0 and (i - 1) not in seen_indices and paragraphs[i - 1].rstrip().endswith(":"):
            text = f"{paragraphs[i - 1]} {text}"
            seen_indices.add(i - 1)
        selected.append(text)
        total += len(text)
    return selected


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
