import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import EvidenceItem, ExtractedClaim, TrustScoreBreakdown, VerificationRun
from app.schemas.nli import NLIVerdict
from app.schemas.trust import ClaimTrustResult
from app.schemas.claim import Claim


async def create_run(session: AsyncSession, *, input_text: str, source_url: str | None) -> VerificationRun:
    run = VerificationRun(input_text=input_text, input_source_url=source_url, status="pending")
    session.add(run)
    await session.flush()
    return run


async def save_claim(session: AsyncSession, *, run_id: uuid.UUID, claim: Claim) -> ExtractedClaim:
    row = ExtractedClaim(
        id=claim.id,
        verification_run_id=run_id,
        claim_text=claim.text,
        claim_order=claim.order,
        entities_json={"entities": [e.model_dump() for e in claim.entities]},
    )
    session.add(row)
    await session.flush()
    return row


async def save_evidence_items(
    session: AsyncSession, *, claim_id: uuid.UUID, verdicts: list[NLIVerdict], selected: set[str]
) -> None:
    for rank, verdict in enumerate(verdicts):
        ev = verdict.evidence
        session.add(
            EvidenceItem(
                claim_id=claim_id,
                source=ev.source,
                title=ev.title,
                url=ev.url,
                snippet=ev.snippet,
                published_date=ev.published_date,
                bm25_score=ev.bm25_score,
                semantic_similarity_score=ev.semantic_similarity_score,
                cross_encoder_score=ev.cross_encoder_score,
                nli_label=verdict.label,
                nli_confidence=verdict.confidence,
                is_selected_for_scoring=ev.url in selected,
                rank_position=rank,
            )
        )
    await session.flush()


async def save_trust_breakdown(session: AsyncSession, *, claim_id: uuid.UUID, result: ClaimTrustResult) -> None:
    session.add(
        TrustScoreBreakdown(
            claim_id=claim_id,
            claim_trust_score=result.trust_score,
            supporting_count=len(result.supporting_evidence),
            contradicting_count=len(result.contradicting_evidence),
            neutral_count=result.breakdown.get("neutral_count", 0),
            source_reliability_weight=result.breakdown.get("source_reliability_weight", 0.0),
            confidence_weight=result.breakdown.get("confidence_weight", 0.0),
            scoring_details_json=result.breakdown,
        )
    )
    await session.flush()


async def complete_run(
    session: AsyncSession,
    *,
    run: VerificationRun,
    trust_score: int,
    verdict_label: str,
    explanation: str,
    duration_ms: int,
) -> None:
    run.status = "completed"
    run.trust_score = trust_score
    run.verdict_label = verdict_label
    run.explanation = explanation
    run.completed_at = datetime.now(timezone.utc)
    run.pipeline_duration_ms = duration_ms
    await session.flush()


async def fail_run(session: AsyncSession, *, run: VerificationRun, error_message: str) -> None:
    run.status = "failed"
    run.error_message = error_message
    run.completed_at = datetime.now(timezone.utc)
    await session.flush()


async def get_run_with_claims(session: AsyncSession, run_id: uuid.UUID) -> VerificationRun | None:
    stmt = (
        select(VerificationRun)
        .where(VerificationRun.id == run_id)
        .options(
            selectinload(VerificationRun.claims).selectinload(ExtractedClaim.evidence_items),
            selectinload(VerificationRun.claims).selectinload(ExtractedClaim.trust_breakdown),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def run_to_verification_response(run: VerificationRun):
    from app.schemas.claim import Claim, ExtractedEntity
    from app.schemas.evidence import EvidenceDocument
    from app.schemas.nli import NLIVerdict
    from app.schemas.ranking import RankedEvidence, RerankedEvidence
    from app.schemas.trust import ClaimTrustResult
    from app.schemas.verification import VerificationResponse

    claim_results = []
    for claim_row in sorted(run.claims, key=lambda c: c.claim_order):
        entities = [
            ExtractedEntity(**e) for e in (claim_row.entities_json or {}).get("entities", [])
        ]
        claim = Claim(id=claim_row.id, text=claim_row.claim_text, order=claim_row.claim_order, entities=entities)

        supporting, contradicting = [], []
        for ev in sorted(claim_row.evidence_items, key=lambda e: e.rank_position or 0):
            reranked = RerankedEvidence(
                source=ev.source,
                title=ev.title,
                url=ev.url,
                snippet=ev.snippet,
                published_date=ev.published_date,
                bm25_score=ev.bm25_score or 0.0,
                semantic_similarity_score=ev.semantic_similarity_score or 0.0,
                cross_encoder_score=ev.cross_encoder_score or 0.0,
            )
            verdict = NLIVerdict(
                evidence=reranked, label=ev.nli_label or "neutral", confidence=ev.nli_confidence or 0.0
            )
            if verdict.label == "entailment":
                supporting.append(verdict)
            elif verdict.label == "contradiction":
                contradicting.append(verdict)

        breakdown = claim_row.trust_breakdown
        breakdown_json = breakdown.scoring_details_json if breakdown else {}
        claim_results.append(
            ClaimTrustResult(
                claim=claim,
                trust_score=breakdown.claim_trust_score if breakdown else 0,
                verdict_label=breakdown_json.get("verdict_label", "unverified"),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                explanation=breakdown_json.get("explanation", ""),
                breakdown=breakdown_json,
            )
        )

    return VerificationResponse(
        run_id=run.id,
        trust_score=run.trust_score or 0,
        verdict_label=run.verdict_label or "unverified",
        explanation=run.explanation or "",
        claims=claim_results,
        created_at=run.created_at,
    )
