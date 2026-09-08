"""Runs one piece of input text through all 9 stages, printing intermediate
state at every step, for demonstration/debugging purposes."""

import asyncio
import sys

from app.pipeline import (
    stage1_input,
    stage2_claim_extraction,
    stage3_evidence_search,
    stage4_bm25_retrieval,
    stage5_semantic_matching,
    stage6_reranking,
    stage7_nli_verification,
    stage7b_evidence_claim_resolution,
    stage8_trust_scoring,
    stage9_explanation,
)
from app.schemas.claim import Claim


async def trace_claim(claim_text: str, order: int):
    print(f"\n{'='*100}")
    print(f"CLAIM {order}: {claim_text}")
    print("=" * 100)

    claim = Claim(text=claim_text, order=order)
    claim.entities = stage3_evidence_search.extract_entities(claim.text)
    print(f"\n[Stage 3a - entity extraction] {[(e.text, e.label) for e in claim.entities]}")

    documents = await stage3_evidence_search.search_all_sources(claim.text, entities=claim.entities)
    print(f"\n[Stage 3b - evidence retrieval] {len(documents)} documents")
    for d in documents:
        print(f"  {d.source:15s} {d.title[:60]}")

    retrieved = stage4_bm25_retrieval.rank_by_bm25(claim.text, documents)
    print(f"\n[Stage 4 - BM25] top 5 by bm25_score:")
    for r in sorted(retrieved, key=lambda x: x.bm25_score, reverse=True)[:5]:
        print(f"  bm25={r.bm25_score:.2f}  {r.title[:60]}")

    ranked = stage5_semantic_matching.rank_by_semantic_similarity(claim.text, retrieved)
    print(f"\n[Stage 5 - semantic + RRF] top 5 by rrf_score:")
    for r in sorted(ranked, key=lambda x: x.rrf_score, reverse=True)[:5]:
        print(f"  rrf={r.rrf_score:.4f} sem={r.semantic_similarity_score:.2f}  {r.title[:60]}")

    reranked = stage6_reranking.rerank(claim.text, ranked)
    print(f"\n[Stage 6 - cross-encoder rerank + dynamic top-k] kept {len(reranked)} documents:")
    for r in reranked:
        print(f"  cross={r.cross_encoder_score:.2f}  {r.source:15s} {r.title[:50]}")
        print(f"     representative_paragraph: {r.representative_paragraph[:120]!r}")

    verdicts = stage7_nli_verification.verify_claim(claim.text, reranked)
    print(f"\n[Stage 7 - NLI verification, first pass]")
    for v in verdicts:
        print(f"  [{v.label:13s} conf={v.confidence:.2f}] {v.evidence.title[:50]}")

    verdicts = await stage7b_evidence_claim_resolution.resolve_ambiguous_verdicts(claim.text, verdicts)
    refined = [v for v in verdicts if v.llm_refined]
    print(f"\n[Stage 7b - LLM evidence-claim resolution] {len(refined)} verdict(s) refined:")
    for v in verdicts:
        if v.resolved_evidence_claim:
            marker = "REFINED" if v.llm_refined else "attempted, no change"
            print(f"  [{marker}] {v.evidence.title[:40]}: {v.resolved_evidence_claim[:100]!r}")
            print(f"     -> final label: {v.label} ({v.confidence:.2f})")

    result = stage8_trust_scoring.score_claim(claim, verdicts)
    print(f"\n[Stage 8 - trust scoring] trust_score={result.trust_score}  verdict={result.verdict_label}")
    print(f"  breakdown: {result.breakdown}")

    explanation = stage9_explanation.generate_explanation(result)
    print(f"\n[Stage 9 - explanation]\n  {explanation}")

    return result


async def main(content: str):
    normalized = stage1_input.normalize_input(content)
    print("[Stage 1 - input normalization]")
    print(f"  input length: {len(content)} -> normalized length: {len(normalized)}")

    claim_texts = stage2_claim_extraction.extract_claims(normalized)
    claims_only = [c.text for c in claim_texts]
    print(f"\n[Stage 2 - claim extraction] {len(claims_only)} claim(s) extracted:")
    for i, c in enumerate(claims_only):
        print(f"  {i}. {c}")

    results = []
    for i, c in enumerate(claims_only):
        results.append(await trace_claim(c, i))

    print(f"\n{'='*100}")
    print("OVERALL SUMMARY")
    print("=" * 100)
    for i, (claim_text, result) in enumerate(zip(claims_only, results)):
        print(f"  {i}. [{result.verdict_label:13s} {result.trust_score:3d}] {claim_text}")


if __name__ == "__main__":
    text = sys.stdin.read()
    asyncio.run(main(text))
