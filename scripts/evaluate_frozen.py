"""Evaluate stages 4-8 against frozen evidence (see snapshot_evidence.py).

Same inputs every run, so a change in accuracy is caused by the code, not by
which documents the free APIs happened to return. Stage 3 (retrieval) is not
exercised - re-snapshot to measure retrieval changes.

Stage 7b's LLM rewrites are cached in evidence_snapshots/llm_cache.json, keyed
by (claim, evidence text): the first run calls the configured LLM, later runs
replay its answers, so 7b stays deterministic until its input changes.
Pass --no-llm to skip 7b entirely.

Usage:
    python scripts/evaluate_frozen.py                        # all snapshots
    python scripts/evaluate_frozen.py --cases eval_claims_v4.json
    python scripts/evaluate_frozen.py --sources google_news,wikipedia,crossref
    python scripts/evaluate_frozen.py --save before.json     # then later:
    python scripts/evaluate_frozen.py --compare before.json  # list verdict flips
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.ml.model_registry import load_all
from app.pipeline import (
    stage4_bm25_retrieval,
    stage5_semantic_matching,
    stage6_reranking,
    stage7_nli_verification,
    stage7b_evidence_claim_resolution,
    stage8_trust_scoring,
)
from app.schemas.claim import Claim, ExtractedEntity
from app.schemas.evidence import EvidenceDocument

SCRIPTS_DIR = Path(__file__).parent
SNAPSHOT_DIR = SCRIPTS_DIR / "evidence_snapshots"
LLM_CACHE_PATH = SNAPSHOT_DIR / "llm_cache.json"
DEFAULT_SOURCES = "google_news,wikipedia"


class CachingLLM:
    """Stands in for get_llm_client() inside stage 7b only."""

    def __init__(self, real_client, cache: dict[str, str]):
        self._real = real_client
        self.cache = cache
        self.misses = 0
        self.failures = 0

    def extract_evidence_claim(self, claim_text: str, evidence_text: str) -> str:
        key = json.dumps([claim_text, evidence_text], ensure_ascii=False)
        if key not in self.cache:
            self.misses += 1
            try:
                self.cache[key] = self._real.extract_evidence_claim(claim_text, evidence_text)
            except Exception:
                # stage 7b swallows this and keeps the first-pass verdict, so
                # without counting it a rate-limited run looks like a real result
                self.failures += 1
                raise
        return self.cache[key]


async def evaluate_case(case: dict, snap: dict, sources: set[str], use_llm: bool) -> dict:
    claim = Claim(
        text=case["claim"], order=0, entities=[ExtractedEntity(**e) for e in snap["entities"]]
    )
    documents = [EvidenceDocument(**d) for d in snap["documents"] if d["source"] in sources]

    retrieved = stage4_bm25_retrieval.rank_by_bm25(claim.text, documents)
    ranked = stage5_semantic_matching.rank_by_semantic_similarity(claim.text, retrieved)
    reranked = stage6_reranking.rerank(claim.text, ranked)
    verdicts = stage7_nli_verification.verify_claim(claim.text, reranked)
    if use_llm:
        verdicts = await stage7b_evidence_claim_resolution.resolve_ambiguous_verdicts(claim.text, verdicts)

    result = stage8_trust_scoring.score_claim(claim, verdicts)
    counts = {label: sum(v.label == label for v in verdicts) for label in ("entailment", "contradiction", "neutral")}
    return {
        "claim": case["claim"],
        "acceptable": case["acceptable"],
        "score": result.trust_score,
        "verdict": result.verdict_label,
        "correct": result.verdict_label in case["acceptable"],
        "counts": counts,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", action="append", help="Snapshot filename; repeatable. Default: all.")
    parser.add_argument("--sources", default=DEFAULT_SOURCES, help=f"Comma-separated. Default: {DEFAULT_SOURCES}")
    parser.add_argument("--no-llm", action="store_true", help="Skip stage 7b.")
    parser.add_argument("--save", help="Write per-claim results to this JSON file.")
    parser.add_argument("--compare", help="A previous --save file; lists claims whose verdict changed.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    load_all()
    sources = set(args.sources.split(","))

    llm = None
    if not args.no_llm:
        from app.clients import get_llm_client

        cache = json.loads(LLM_CACHE_PATH.read_text()) if LLM_CACHE_PATH.exists() else {}
        llm = CachingLLM(get_llm_client(), cache)
        stage7b_evidence_claim_resolution.get_llm_client = lambda: llm

    names = args.cases or sorted(p.name for p in SNAPSHOT_DIR.glob("eval_claims*.json"))
    if not names:
        raise SystemExit("No snapshots found - run scripts/snapshot_evidence.py first.")

    all_results: list[dict] = []
    for name in names:
        cases = json.loads((SCRIPTS_DIR / name).read_text())
        snaps = {s["claim"]: s for s in json.loads((SNAPSHOT_DIR / name).read_text())}
        print(name)
        file_results = []
        for case in cases:
            snap = snaps.get(case["claim"])
            if snap is None:
                print(f"  SKIP  no snapshot for {case['claim'][:60]} - re-run snapshot_evidence.py")
                continue
            r = await evaluate_case(case, snap, sources, use_llm=llm is not None)
            file_results.append(r)
            if not r["correct"]:
                c = r["counts"]
                print(
                    f"  FAIL {r['score']:>4}  {r['verdict']:<13} (want {'/'.join(r['acceptable'])})  "
                    f"S{c['entailment']} C{c['contradiction']} N{c['neutral']}  {r['claim'][:60]}"
                )
        passed = sum(r["correct"] for r in file_results)
        print(f"  {passed}/{len(file_results)} correct")
        all_results.extend(file_results)

    passed = sum(r["correct"] for r in all_results)
    print(f"\nTOTAL {passed}/{len(all_results)} correct ({100 * passed / max(len(all_results), 1):.0f}%)")

    if llm is not None:
        LLM_CACHE_PATH.write_text(json.dumps(llm.cache, indent=1, ensure_ascii=False))
        if llm.misses:
            print(f"({llm.misses - llm.failures} new stage-7b LLM calls cached)")
        if llm.failures:
            print(
                f"WARNING: {llm.failures} stage-7b LLM calls failed (rate limit?) - those documents kept their "
                "first-pass verdicts, so this run is not comparable to one where they succeeded. "
                "Re-run later to fill the cache, or use --no-llm."
            )

    if args.save:
        Path(args.save).write_text(json.dumps(all_results, indent=1, ensure_ascii=False))

    if args.compare:
        before = {r["claim"]: r for r in json.loads(Path(args.compare).read_text())}
        flips = [
            (before[r["claim"]], r)
            for r in all_results
            if r["claim"] in before and before[r["claim"]]["verdict"] != r["verdict"]
        ]
        print(f"\n{len(flips)} verdict change(s) vs {args.compare}:")
        for old, new in flips:
            arrow = "FIXED" if new["correct"] and not old["correct"] else "BROKE" if old["correct"] and not new["correct"] else "moved"
            print(f"  {arrow:<5} {old['verdict']}({old['score']}) -> {new['verdict']}({new['score']})  {new['claim'][:60]}")


if __name__ == "__main__":
    asyncio.run(main())
