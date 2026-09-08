import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import PipelineError
from app.db import repository
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
from app.schemas.trust import ClaimTrustResult
from app.schemas.verification import VerificationResponse

logger = logging.getLogger(__name__)

LIKELY_TRUE_THRESHOLD = 70
LIKELY_FALSE_THRESHOLD = 30


async def _process_claim(
    claim_text: str, order: int, session: AsyncSession, run_id, use_llm_explanation: bool = True
) -> ClaimTrustResult:
    from app.schemas.claim import Claim

    claim = Claim(text=claim_text, order=order)
    claim.entities = await asyncio.to_thread(stage3_evidence_search.extract_entities, claim.text)
    await repository.save_claim(session, run_id=run_id, claim=claim)

    # Wikidata resolution only feeds trust scoring (stage8), which runs well
    # after this - so it runs alongside evidence retrieval instead of before
    # it, adding no latency of its own as long as it fits in that window.
    documents, claim.entities = await asyncio.gather(
        stage3_evidence_search.search_all_sources(claim.text, entities=claim.entities),
        stage3_evidence_search.enrich_entities_with_wikidata(claim.entities),
    )
    retrieved = await asyncio.to_thread(stage4_bm25_retrieval.rank_by_bm25, claim.text, documents)
    ranked = await asyncio.to_thread(stage5_semantic_matching.rank_by_semantic_similarity, claim.text, retrieved)
    reranked = await asyncio.to_thread(stage6_reranking.rerank, claim.text, ranked)
    verdicts = await asyncio.to_thread(stage7_nli_verification.verify_claim, claim.text, reranked)
    if get_settings().evidence_claim_resolution_enabled:
        try:
            verdicts = await stage7b_evidence_claim_resolution.resolve_ambiguous_verdicts(claim.text, verdicts)
        except Exception:
            # a failure here should cost the claim its LLM-refined verdicts,
            # not the claim itself - fall back to stage 7's first-pass results
            logger.exception("Evidence-claim resolution failed for claim %r; keeping first-pass verdicts", claim.text)

    selected_urls = {v.evidence.url for v in verdicts}
    await repository.save_evidence_items(session, claim_id=claim.id, verdicts=verdicts, selected=selected_urls)

    result = stage8_trust_scoring.score_claim(claim, verdicts)
    if verdicts and use_llm_explanation:
        try:
            result.explanation = await asyncio.to_thread(stage9_explanation.generate_explanation, result)
        except Exception:
            # a Gemini hiccup on the narration step shouldn't discard the
            # evidence gathering/scoring work already done for this claim
            logger.exception("Explanation generation failed for claim %r; using fallback text", claim.text)
            result.explanation = stage9_explanation.build_deterministic_explanation(result)
    else:
        result.explanation = stage9_explanation.build_deterministic_explanation(result)
    result.breakdown["explanation"] = result.explanation

    await repository.save_trust_breakdown(session, claim_id=claim.id, result=result)
    return result


def _aggregate(claim_results: list[ClaimTrustResult]) -> tuple[int, str, str]:
    if not claim_results:
        return 50, "unverified", "No checkable factual claims were found in the submitted content."

    if len(claim_results) == 1:
        only = claim_results[0]
        return only.trust_score, only.verdict_label, only.explanation

    avg_score = round(sum(r.trust_score for r in claim_results) / len(claim_results))
    if all(r.verdict_label == "unverified" for r in claim_results):
        label = "unverified"
    elif avg_score >= LIKELY_TRUE_THRESHOLD:
        label = "likely_true"
    elif avg_score <= LIKELY_FALSE_THRESHOLD:
        label = "likely_false"
    else:
        label = "mixed"

    explanation = " ".join(
        f"Claim {i + 1} ({r.trust_score}/100, {r.verdict_label}): {r.explanation}"
        for i, r in enumerate(claim_results)
    )
    return avg_score, label, explanation


async def _verify_claims(
    claim_texts_provider,
    *,
    input_text: str,
    source_url: str | None,
    session: AsyncSession,
    use_llm_explanation: bool,
) -> VerificationResponse:
    start = time.monotonic()
    run = await repository.create_run(session, input_text=input_text, source_url=source_url)
    await session.commit()

    try:
        claim_texts = await claim_texts_provider()

        claim_results = []
        for i, text in enumerate(claim_texts):
            result = await _process_claim(
                text, i, session, run.id, use_llm_explanation=use_llm_explanation
            )
            claim_results.append(result)

        trust_score, verdict_label, explanation = _aggregate(claim_results)
        duration_ms = int((time.monotonic() - start) * 1000)

        await repository.complete_run(
            session,
            run=run,
            trust_score=trust_score,
            verdict_label=verdict_label,
            explanation=explanation,
            duration_ms=duration_ms,
        )
        await session.commit()

        return VerificationResponse(
            run_id=run.id,
            trust_score=trust_score,
            verdict_label=verdict_label,
            explanation=explanation,
            claims=claim_results,
            created_at=run.created_at,
        )
    except Exception as exc:
        logger.exception("Pipeline failed for run %s", run.id)
        await repository.fail_run(session, run=run, error_message=str(exc))
        await session.commit()
        raise PipelineError(str(exc)) from exc


async def run_verification(content: str, source_url: str | None, session: AsyncSession) -> VerificationResponse:
    normalized = stage1_input.normalize_input(content)

    async def extract():
        return await asyncio.to_thread(
            lambda: [c.text for c in stage2_claim_extraction.extract_claims(normalized)]
        )

    return await _verify_claims(
        extract,
        input_text=normalized,
        source_url=source_url,
        session=session,
        use_llm_explanation=True,
    )


async def run_claim_verification(
    claim_text: str, source_url: str | None, session: AsyncSession, use_llm_explanation: bool = False
) -> VerificationResponse:
    """Verify a single, already-isolated claim.

    Skips LLM claim extraction (stage 2) - the caller supplies the claim - and
    by default skips LLM narration (stage 9) too, so the retrieval → ranking →
    NLI → scoring path can be exercised without any external LLM dependency.
    """
    normalized = stage1_input.normalize_input(claim_text)

    async def single_claim():
        return [normalized]

    return await _verify_claims(
        single_claim,
        input_text=normalized,
        source_url=source_url,
        session=session,
        use_llm_explanation=use_llm_explanation,
    )
