import asyncio
import logging

from app.clients import gdelt_client, semantic_scholar_client, wikipedia_client
from app.config import get_settings
from app.ml.model_registry import get_spacy_nlp
from app.schemas.claim import ExtractedEntity
from app.schemas.evidence import EvidenceDocument

logger = logging.getLogger(__name__)

RELEVANT_LABELS = {"PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "NORP", "FAC"}


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


async def search_all_sources(
    claim_text: str,
    *,
    entities: list[ExtractedEntity] | None = None,
    sources: tuple[str, ...] = ("gdelt", "semantic_scholar", "wikipedia"),
) -> list[EvidenceDocument]:
    """Query the requested evidence sources concurrently; a failing source is
    logged and skipped rather than failing the whole claim."""
    source_calls = {
        "gdelt": gdelt_client.search,
        "semantic_scholar": semantic_scholar_client.search,
        "wikipedia": wikipedia_client.search,
    }
    tasks = [source_calls[s](claim_text) for s in sources if s in source_calls]
    task_names = [s for s in sources if s in source_calls]

    entity_query = build_entity_query(entities or [])
    if entity_query and entity_query.lower() != claim_text.lower() and "wikipedia" in sources:
        tasks.append(wikipedia_client.search(entity_query))
        task_names.append("wikipedia(entities)")

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
    return docs


async def _gather_within_deadline(tasks, task_names, claim_text):
    """Run every source concurrently, waiting only as long as it is useful.

    These are free, aggressively throttled APIs: GDELT was measured taking
    17.8s to return a 429, which by itself accounted for most of a request's
    latency while contributing no evidence. But a flat deadline is the wrong
    instrument - cutting it to 0.8s starved 9 of 22 requests of evidence
    entirely and dropped accuracy from 87% to 40%, because the one source
    that does answer needs ~0.7s.

    So the wait is adaptive: once any source has returned, the rest get a
    short grace period and are then abandoned; if nothing has come back yet,
    waiting longer is strictly better than answering with no evidence, so the
    hard cap applies instead.
    """
    settings = get_settings()
    wrapped = [asyncio.ensure_future(t) for t in tasks]
    pending = set(wrapped)
    done: set = set()
    deadline = settings.evidence_deadline_seconds

    while pending:
        timeout = settings.evidence_grace_seconds if done else deadline
        just_done, pending = await asyncio.wait(
            pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if not just_done:
            break  # nothing new arrived within the window
        done |= just_done

    for task, name in zip(wrapped, task_names):
        if task in pending:
            task.cancel()
            logger.warning("Evidence source %r was too slow for claim %r; continuing without it", name, claim_text)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    return [task.exception() or task.result() if task in done else None for task in wrapped]
