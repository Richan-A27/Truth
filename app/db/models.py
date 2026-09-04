import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_text: Mapped[str] = mapped_column(Text)
    input_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(default="pending")
    trust_score: Mapped[int | None] = mapped_column(nullable=True)
    verdict_label: Mapped[str | None] = mapped_column(nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pipeline_duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    claims: Mapped[list["ExtractedClaim"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ExtractedClaim(Base):
    __tablename__ = "extracted_claims"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verification_runs.id"))
    claim_text: Mapped[str] = mapped_column(Text)
    claim_order: Mapped[int]
    entities_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    run: Mapped["VerificationRun"] = relationship(back_populates="claims")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    trust_breakdown: Mapped["TrustScoreBreakdown"] = relationship(
        back_populates="claim", uselist=False, cascade="all, delete-orphan"
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extracted_claims.id"))
    source: Mapped[str]
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str] = mapped_column(Text)
    published_date: Mapped[datetime | None] = mapped_column(nullable=True)
    bm25_score: Mapped[float | None] = mapped_column(nullable=True)
    semantic_similarity_score: Mapped[float | None] = mapped_column(nullable=True)
    cross_encoder_score: Mapped[float | None] = mapped_column(nullable=True)
    nli_label: Mapped[str | None] = mapped_column(nullable=True)
    nli_confidence: Mapped[float | None] = mapped_column(nullable=True)
    is_selected_for_scoring: Mapped[bool] = mapped_column(default=False)
    rank_position: Mapped[int | None] = mapped_column(nullable=True)

    claim: Mapped["ExtractedClaim"] = relationship(back_populates="evidence_items")


class TrustScoreBreakdown(Base):
    __tablename__ = "trust_score_breakdown"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extracted_claims.id"), unique=True)
    claim_trust_score: Mapped[int]
    supporting_count: Mapped[int]
    contradicting_count: Mapped[int]
    neutral_count: Mapped[int]
    source_reliability_weight: Mapped[float]
    confidence_weight: Mapped[float]
    scoring_details_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    claim: Mapped["ExtractedClaim"] = relationship(back_populates="trust_breakdown")
