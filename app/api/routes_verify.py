import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PipelineError
from app.db.database import get_session
from app.db.repository import get_run_with_claims, run_to_verification_response
from app.pipeline import stage1_input
from app.pipeline.orchestrator import run_claim_verification, run_verification
from app.schemas.verification import (
    ClaimVerificationRequest,
    VerificationRequest,
    VerificationResponse,
)

router = APIRouter()


@router.post("/verify", response_model=VerificationResponse)
async def verify(request: VerificationRequest, session: AsyncSession = Depends(get_session)):
    try:
        stage1_input.normalize_input(request.content)
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return await run_verification(request.content, request.source_url, session)
    except PipelineError as exc:
        raise HTTPException(status_code=500, detail=f"Verification pipeline failed: {exc}") from exc


@router.post("/verify/claim", response_model=VerificationResponse)
async def verify_claim(request: ClaimVerificationRequest, session: AsyncSession = Depends(get_session)):
    """Verify a single claim that the caller has already isolated, skipping
    LLM claim extraction (and, by default, LLM narration)."""
    try:
        stage1_input.normalize_input(request.claim)
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return await run_claim_verification(
            request.claim,
            request.source_url,
            session,
            use_llm_explanation=request.use_llm_explanation,
        )
    except PipelineError as exc:
        raise HTTPException(status_code=500, detail=f"Verification pipeline failed: {exc}") from exc


@router.get("/verify/{run_id}", response_model=VerificationResponse)
async def get_verification(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    run = await get_run_with_claims(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="verification run not found")
    return run_to_verification_response(run)
