"""Runs the named regression claims through the FULL stage3->stage7
pipeline (all existing heuristics intact - relevance floor, hedge
detection, question detection, sentence selection, asymmetric thresholds)
twice: once with the current NLI model, once with the fact_verification
model. Everything except the model itself is held identical.
"""

import asyncio

from app.pipeline import (
    stage3_evidence_search,
    stage4_bm25_retrieval,
    stage5_semantic_matching,
    stage6_reranking,
    stage7_nli_verification,
    stage8_trust_scoring,
)
from app.schemas.claim import Claim

CASES = [
    ("Bats are completely blind.", "likely_false"),
    ("Albert Einstein developed the theory of general relativity.", "likely_true"),
    ("The Moon is made of green cheese.", "likely_false"),
    ("William Shakespeare wrote the play Hamlet.", "likely_true"),
    ("The Great Wall of China is visible from space with the naked eye.", "likely_false"),
    ("Photosynthesis in plants primarily occurs in the roots.", "likely_false"),
    ("The Earth is flat.", "likely_false"),
]


async def _run(claim_text: str, nli_variant: str):
    entities = stage3_evidence_search.extract_entities(claim_text)
    documents = await stage3_evidence_search.search_all_sources(claim_text, entities=entities)
    retrieved = stage4_bm25_retrieval.rank_by_bm25(claim_text, documents)
    ranked = stage5_semantic_matching.rank_by_semantic_similarity(claim_text, retrieved)
    reranked = stage6_reranking.rerank(claim_text, ranked)
    verdicts = stage7_nli_verification.verify_claim(claim_text, reranked, nli_variant=nli_variant)
    claim = Claim(text=claim_text, order=0)
    result = stage8_trust_scoring.score_claim(claim, verdicts)
    label_counts = {}
    for v in verdicts:
        label_counts[v.label] = label_counts.get(v.label, 0) + 1
    return result.trust_score, result.verdict_label, label_counts


async def main():
    print(f"{'claim':65s} {'expected':13s} {'current':22s} {'fact_verification':22s}")
    print("-" * 130)
    for claim_text, expected in CASES:
        current_score, current_label, current_counts = await _run(claim_text, "current")
        fv_score, fv_label, fv_counts = await _run(claim_text, "fact_verification")
        print(f"{claim_text[:63]:65s} {expected:13s} {f'{current_score} {current_label}':22s} {f'{fv_score} {fv_label}':22s}")
        print(f"   current counts: {current_counts}   fact_verification counts: {fv_counts}")


if __name__ == "__main__":
    asyncio.run(main())
