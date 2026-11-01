"""Freeze each eval claim's retrieved evidence to disk, so ranking/NLI/scoring
changes can be measured against identical inputs (see evaluate_frozen.py).

Live evals can't separate small changes: the free sources return slightly
different documents run to run, and that alone flips about ±2 borderline
claims out of 68 - the same size as most real improvements.

Snapshots every source - including ones dropped from the default pool, such as
OpenAlex and CrossRef - with a long grace period so slow sources aren't cut off
by the race. The evaluator filters to whichever sources you ask for, so a
source can be re-evaluated later without refetching.

Usage:
    python scripts/snapshot_evidence.py                     # all eval_claims*.json
    python scripts/snapshot_evidence.py --cases eval_claims_v4.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.pipeline import stage3_evidence_search

SCRIPTS_DIR = Path(__file__).parent
SNAPSHOT_DIR = SCRIPTS_DIR / "evidence_snapshots"
ALL_SOURCES = ("openalex", "crossref", "google_news", "wikipedia")


async def snapshot_claim(claim_text: str) -> dict:
    entities = stage3_evidence_search.extract_entities(claim_text)
    documents, entities = await asyncio.gather(
        stage3_evidence_search.search_all_sources(claim_text, entities=entities, sources=ALL_SOURCES),
        stage3_evidence_search.enrich_entities_with_wikidata(entities),
    )
    return {
        "claim": claim_text,
        "entities": [e.model_dump() for e in entities],
        "documents": [d.model_dump(mode="json") for d in documents],
    }


async def snapshot_file(cases_name: str, delay: float) -> None:
    cases = json.loads((SCRIPTS_DIR / cases_name).read_text())
    snapshots = []
    for i, case in enumerate(cases):
        if i and delay:
            await asyncio.sleep(delay)  # Wikipedia rate-limits back-to-back batches
        snap = await snapshot_claim(case["claim"])
        counts: dict[str, int] = {}
        for doc in snap["documents"]:
            counts[doc["source"]] = counts.get(doc["source"], 0) + 1
        print(f"  {len(snap['documents']):>3} docs {counts}  {case['claim'][:60]}")
        snapshots.append(snap)

    SNAPSHOT_DIR.mkdir(exist_ok=True)
    out = SNAPSHOT_DIR / cases_name
    out.write_text(json.dumps(snapshots, indent=1, ensure_ascii=False))
    print(f"wrote {out.relative_to(SCRIPTS_DIR.parent)}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", action="append", help="Filename under scripts/; repeatable. Default: all.")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    # give every source time to answer - this runs once, offline, not per request
    get_settings().evidence_grace_seconds = get_settings().evidence_deadline_seconds

    names = args.cases or sorted(p.name for p in SCRIPTS_DIR.glob("eval_claims*.json"))
    for name in names:
        print(name)
        await snapshot_file(name, args.delay)


if __name__ == "__main__":
    asyncio.run(main())
