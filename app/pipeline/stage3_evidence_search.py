import asyncio
import logging

from app.clients import (
    crossref_client,
    gdelt_client,
    get_llm_client,
    google_news_client,
    openalex_client,
    semantic_scholar_client,
    wikidata_client,
    wikipedia_client,
)
from app.config import get_settings
from app.ml.model_registry import get_spacy_nlp
from app.schemas.claim import ExtractedEntity
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

# Must be a superset of _QUERYABLE_LABELS below - WORK_OF_ART and PRODUCT
# were queryable but not extracted, so entity_query silently dropped titles
# like "Hamlet" from "William Shakespeare wrote the play Hamlet.": spaCy
# tagged it correctly, but it never survived extract_entities to reach
# build_entity_query. The diffuse full-sentence query that filled the gap
# surfaces pop-culture adaptations (a Radiohead-scored production, a 1996
# film) instead of the play itself - harmless with a thin intro, but deep
# fetch (see wikipedia_client) gives those adaptations enough claim-relevant
# text to be scored as confident entailment, measurably softening what
# should be a clean verdict into "mixed".
RELEVANT_LABELS = {"PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "NORP", "FAC", "WORK_OF_ART", "PRODUCT"}


def extract_entities(claim_text: str) -> list[ExtractedEntity]:
    nlp = get_spacy_nlp()
    doc = nlp(claim_text)
    return [
        ExtractedEntity(text=ent.text, label=ent.label_)
        for ent in doc.ents
        if ent.label_ in RELEVANT_LABELS
    ]


# Entity types worth turning into a focused lookup. Dates and bare numbers
# make poor search queries on their own.
_QUERYABLE_LABELS = {"PERSON", "ORG", "GPE", "LOC", "FAC", "EVENT", "WORK_OF_ART", "NORP", "PRODUCT"}


async def enrich_entities_with_wikidata(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Resolve a Wikidata description for each entity worth disambiguating.

    Meant to run concurrently with evidence retrieval (via asyncio.gather in
    the orchestrator), not before it - only trust scoring needs the
    description, and stages 3-7 don't, so a slow or failed lookup adds no
    latency of its own as long as it finishes within that window. A lookup
    that fails or times out just leaves that entity without a description
    rather than blocking the claim.
    """
    queryable = [e for e in entities if e.label in _QUERYABLE_LABELS]
    if not queryable:
        return entities

    async def resolve_one(entity: ExtractedEntity) -> ExtractedEntity:
        try:
            description = await wikidata_client.resolve_description(entity.text)
        except Exception as exc:  # noqa: BLE001 - a failed lookup should not fail the claim
            logger.warning("Wikidata resolution failed for %r: %s", entity.text, exc)
            description = None
        return entity.model_copy(update={"wikidata_description": description})

    resolved = await asyncio.gather(*(resolve_one(e) for e in queryable))
    resolved_by_text = {e.text: e for e in resolved}
    return [resolved_by_text.get(e.text, e) for e in entities]


# Below this many tokens, an entity query is considered too weak to trust -
# e.g. "Vaccines cause autism" tags "Vaccines" as NORP and "autism" as
# nothing, so the entity query is just "Vaccines" alone and never finds the
# actual controversy article.
MIN_QUERY_TOKENS = 2

# The LLM query fallback (~2-8s with Ollama) is far slower than the
# evidence_deadline_seconds/grace race the other sources run under (a fast
# source answering leaves stragglers only ~0.25s before they're cancelled -
# see _gather_within_deadline). Racing it there would mean it almost never
# gets to contribute. It runs separately instead, with its own generous
# budget, and only for the minority of claims whose entity query is weak -
# well-anchored claims never pay this latency at all.
LLM_QUERY_TIMEOUT_SECONDS = 15.0

# Wikipedia now does a second, slower pass per candidate (see
# wikipedia_client._fetch_deep_content) to pull claim-relevant paragraphs
# from deeper in the article, not just the lead section - typically ~2s,
# well past what the fast race's grace period allows a straggler. It gets
# the same treatment as the LLM fallback above: its own generous, separately
# awaited budget instead of a seat in the race.
WIKIPEDIA_TASK_TIMEOUT_SECONDS = 6.0


async def _wikipedia_search(query: str) -> list[EvidenceDocument]:
    try:
        return await asyncio.wait_for(wikipedia_client.search(query), timeout=WIKIPEDIA_TASK_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - a slow/failed Wikipedia call should not fail the claim
        logger.warning("Wikipedia search failed for query %r: %s", query, exc)
        return []


async def _llm_augmented_search(claim_text: str) -> list[EvidenceDocument]:
    try:
        query = await asyncio.wait_for(
            asyncio.to_thread(get_llm_client().generate_search_query, claim_text),
            timeout=LLM_QUERY_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - a failed/slow query should not fail the claim
        logger.warning("LLM search-query generation failed for claim %r: %s", claim_text, exc)
        return []
    if not query:
        return []
    try:
        return await wikipedia_client.search(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM-augmented search failed for claim %r (query %r): %s", claim_text, query, exc)
        return []


def build_entity_query(entities: list[ExtractedEntity]) -> str:
    """A query of just the claim's named entities.

    A whole claim sentence is a diffuse full-text query: searching
    "William Shakespeare wrote the play Hamlet." surfaced a Radiohead stage
    production and Shakespeare's son Hamnet, but never the Hamlet article.
    The entity-only query "William Shakespeare Hamlet" retrieves the
    canonical pages instead.
    """
    seen, terms = set(), []
    for entity in entities:
        if entity.label not in _QUERYABLE_LABELS:
            continue
        key = entity.text.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(entity.text)
    return " ".join(terms)


def build_subject_query(claim_text: str) -> str:
    """The claim's grammatical subject, minus leading determiners - a topic
    query for claims with no usable named entities. "The speed of light is
    approximately 300,000 kilometers per second." has no entities at all, so
    the only Wikipedia queries were the whole sentence (which surfaced Ole
    Rømer and "Speed of electricity") and the LLM's query; "speed of light"
    retrieves the canonical article directly."""
    doc = get_spacy_nlp()(claim_text)
    subject = next((t for t in doc if t.dep_ in ("nsubj", "nsubjpass")), None)
    if subject is None or subject.pos_ == "PRON":
        return ""
    tokens = [t for t in subject.subtree if t.dep_ != "punct"]
    while tokens and tokens[0].dep_ == "det":
        tokens = tokens[1:]
    if not tokens:
        return ""
    return doc[tokens[0].i : tokens[-1].i + 1].text


async def search_all_sources(
    claim_text: str,
    *,
    entities: list[ExtractedEntity] | None = None,
    # GDELT and Semantic Scholar dropped from the default pool: GDELT is
    # frequently unreachable outright (ConnectTimeout, confirmed live - not
    # a timeout-tuning issue, it genuinely can't connect) and Semantic
    # Scholar's anonymous tier 429s intermittently even with a key (free-tier
    # quota, not a bug - confirmed by isolated calls succeeding minutes apart
    # from ones that don't). OpenAlex, CrossRef, and Google News replace
    # them: all three tested reliably healthy, need no API key, and cover
    # the same two roles (academic + news) that GDELT/Semantic Scholar did.
    #
    # OpenAlex and CrossRef have since been dropped too. Measured over the 37
    # eval claims, CrossRef cast 11 non-neutral votes and 7 were wrong: paper
    # titles that quote a myth verbatim ("The moon is made of green cheese.")
    # score as near-certain entailment, as do off-topic papers. It was the
    # sole cause of the green-cheese miss. OpenAlex mostly lost the race to
    # Google News's grace period and contributed nothing. Academic abstracts
    # rarely state everyday facts plainly, which is what NLI needs.
    # Still callable explicitly via `sources=`.
    sources: tuple[str, ...] = ("google_news", "wikipedia"),
) -> list[EvidenceDocument]:
    """Query the requested evidence sources concurrently; a failing source is
    logged and skipped rather than failing the whole claim."""
    fast_source_calls = {
        "gdelt": gdelt_client.search,
        "semantic_scholar": semantic_scholar_client.search,
        "openalex": openalex_client.search,
        "crossref": crossref_client.search,
        "google_news": google_news_client.search,
    }
    tasks = [fast_source_calls[s](claim_text) for s in sources if s in fast_source_calls]
    task_names = [s for s in sources if s in fast_source_calls]

    entity_query = build_entity_query(entities or [])

    # Wikipedia runs outside the fast race (see _wikipedia_search /
    # WIKIPEDIA_TASK_TIMEOUT_SECONDS) - scheduled now so it progresses
    # concurrently with everything else, awaited after the race below.
    wikipedia_tasks: list[asyncio.Future] = []
    if "wikipedia" in sources:
        wikipedia_tasks.append(asyncio.ensure_future(_wikipedia_search(claim_text)))
        if entity_query and entity_query.lower() != claim_text.lower():
            wikipedia_tasks.append(asyncio.ensure_future(_wikipedia_search(entity_query)))
        if len(entity_query.split()) < MIN_QUERY_TOKENS:
            subject_query = build_subject_query(claim_text)
            if subject_query and subject_query.lower() not in (entity_query.lower(), claim_text.lower()):
                wikipedia_tasks.append(asyncio.ensure_future(_wikipedia_search(subject_query)))

    # Scheduled now (not awaited) so it runs concurrently with the fast-source
    # race below rather than adding its own latency on top - total added time
    # for a weak-query claim is roughly max(race_time, llm_time), not the sum.
    llm_query_task = None
    if len(entity_query.split()) < MIN_QUERY_TOKENS and "wikipedia" in sources:
        llm_query_task = asyncio.ensure_future(_llm_augmented_search(claim_text))

    results = await _gather_within_deadline(tasks, task_names, claim_text)

    docs: list[EvidenceDocument] = []
    seen_urls: set[str] = set()
    for name, result in zip(task_names, results):
        if result is None:
            continue
        if isinstance(result, Exception):
            logger.warning("Evidence source %r failed for claim %r: %s", name, claim_text, result)
            continue
        for doc in result:
            # the same page can surface from more than one source; counting it
            # twice would double its influence on the trust score
            if doc.url in seen_urls:
                continue
            seen_urls.add(doc.url)
            docs.append(doc)

    for wiki_task in wikipedia_tasks:
        for doc in await wiki_task:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                docs.append(doc)

    if llm_query_task is not None:
        for doc in await llm_query_task:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                docs.append(doc)

    return docs


async def _gather_within_deadline(tasks, task_names, claim_text):
    """Run every source concurrently, waiting only as long as it is useful.

    These are free, aggressively throttled APIs: GDELT was measured taking
    17.8s to return a 429, which by itself accounted for most of a request's
    latency while contributing no evidence. But a flat deadline is the wrong
    instrument - cutting it to 0.8s starved 9 of 22 requests of evidence
    entirely and dropped accuracy from 87% to 40%, because the one source
    that does answer needs ~0.7s.

    So the wait is adaptive: once any source has *succeeded*, the rest get a
    short grace period and are then abandoned; if nothing has succeeded yet,
    waiting longer is strictly better than answering with no evidence, so the
    hard cap applies instead.

    Deliberately keyed on success, not mere completion: Semantic Scholar's
    429 (~0.85s) and Wikipedia's own success (~0.8s) used to land close
    enough together that a fast *failure* here would start the 0.25s grace
    countdown and cancel Wikipedia's still-pending call a hair before it
    finished - discarding real evidence because an unrelated source got
    rejected quickly. Measured impact: re-adding Semantic Scholar to the
    default pool dropped a 22-claim eval from 67% to 45% before this fix.
    Wikipedia has since moved out of this race entirely (see
    search_all_sources) now that its own deep-fetch pass is too slow for it,
    but the same failure mode remains possible between any two sources still
    in the race, which is why success - not completion - is still the right
    thing to key on.
    """
    settings = get_settings()
    wrapped = [asyncio.ensure_future(t) for t in tasks]
    pending = set(wrapped)
    done: set = set()
    succeeded = False
    deadline = settings.evidence_deadline_seconds

    while pending:
        timeout = settings.evidence_grace_seconds if succeeded else deadline
        just_done, pending = await asyncio.wait(
            pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if not just_done:
            break  # nothing new arrived within the window
        done |= just_done
        succeeded = succeeded or any(task.exception() is None for task in just_done)

    for task, name in zip(wrapped, task_names):
        if task in pending:
            task.cancel()
            logger.warning("Evidence source %r was too slow for claim %r; continuing without it", name, claim_text)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    return [task.exception() or task.result() if task in done else None for task in wrapped]
