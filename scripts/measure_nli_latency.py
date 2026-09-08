"""Isolated NLI-stage latency comparison: times only stage7_nli_verification
.verify_claim() itself against real, already-reranked evidence sets, so
Ollama/network time (which dominates a full /verify request) doesn't drown
out the one number this actually measures - the model's own inference cost.
"""

import asyncio
import time

from app.pipeline import stage3_evidence_search, stage4_bm25_retrieval, stage5_semantic_matching, stage6_reranking
from app.pipeline import stage7_nli_verification

CLAIMS = [
    "Bats are completely blind.",
    "Albert Einstein developed the theory of general relativity.",
    "The Moon is made of green cheese.",
    "William Shakespeare wrote the play Hamlet.",
    "The Great Wall of China is visible from space with the naked eye.",
    "Photosynthesis in plants primarily occurs in the roots.",
    "The Earth is flat.",
]


async def _reranked_for(claim_text: str):
    entities = stage3_evidence_search.extract_entities(claim_text)
    documents = await stage3_evidence_search.search_all_sources(claim_text, entities=entities)
    retrieved = stage4_bm25_retrieval.rank_by_bm25(claim_text, documents)
    ranked = stage5_semantic_matching.rank_by_semantic_similarity(claim_text, retrieved)
    return stage6_reranking.rerank(claim_text, ranked)


async def main():
    reranked_sets = [(claim, await _reranked_for(claim)) for claim in CLAIMS]

    for variant in ("current", "fact_verification"):
        # one warm call so model loading isn't counted in the measured pass
        stage7_nli_verification.verify_claim(CLAIMS[0], reranked_sets[0][1], nli_variant=variant)

        times = []
        for claim, reranked in reranked_sets:
            start = time.perf_counter()
            stage7_nli_verification.verify_claim(claim, reranked, nli_variant=variant)
            times.append(time.perf_counter() - start)

        mean_ms = sum(times) / len(times) * 1000
        print(f"{variant:20s} mean={mean_ms:.1f}ms  min={min(times)*1000:.1f}ms  max={max(times)*1000:.1f}ms  n={len(times)} claims")


if __name__ == "__main__":
    asyncio.run(main())
