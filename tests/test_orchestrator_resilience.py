import uuid

from app.pipeline import orchestrator
from app.schemas.claim import ExtractedEntity
from app.schemas.evidence import EvidenceDocument
from app.schemas.nli import NLIVerdict
from app.schemas.ranking import RerankedEvidence


def _fake_verdict() -> NLIVerdict:
    evidence = RerankedEvidence(
        source="wikipedia", title="t", url="https://example.com/1", snippet="s", cross_encoder_score=1.0
    )
    return NLIVerdict(evidence=evidence, label="entailment", confidence=0.9)


async def test_explanation_failure_falls_back_instead_of_raising(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.extract_entities", lambda text: [ExtractedEntity(text="x", label="GPE")]
    )
    monkeypatch.setattr("app.db.repository.save_claim", _async_noop)

    async def fake_search(claim_text, *, entities=None, sources=None):
        return [EvidenceDocument(source="wikipedia", title="t", url="https://example.com/1", snippet="s")]

    monkeypatch.setattr("app.pipeline.stage3_evidence_search.search_all_sources", fake_search)
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.enrich_entities_with_wikidata", lambda entities: _async_return(entities)
    )
    monkeypatch.setattr("app.pipeline.stage4_bm25_retrieval.rank_by_bm25", lambda claim_text, docs: _to_retrieved(docs))
    monkeypatch.setattr(
        "app.pipeline.stage5_semantic_matching.rank_by_semantic_similarity",
        lambda claim_text, docs: [_to_ranked(d) for d in docs],
    )
    monkeypatch.setattr(
        "app.pipeline.stage6_reranking.rerank", lambda claim_text, docs, top_k=5: [_to_reranked(d) for d in docs]
    )
    monkeypatch.setattr("app.pipeline.stage7_nli_verification.verify_claim", lambda claim_text, docs: [_fake_verdict()])
    monkeypatch.setattr("app.db.repository.save_evidence_items", _async_noop)
    monkeypatch.setattr("app.db.repository.save_trust_breakdown", _async_noop)

    def raise_gemini_error(result):
        raise RuntimeError("Gemini quota exceeded")

    monkeypatch.setattr("app.pipeline.stage9_explanation.generate_explanation", raise_gemini_error)

    result = await orchestrator._process_claim("Some claim", 0, session=None, run_id=uuid.uuid4())

    # falls back to the deterministic explanation instead of failing the claim
    assert "Some claim" in result.explanation
    assert "supporting" in result.explanation
    assert result.trust_score > 50  # entailment verdict still scored normally


def _stub_pipeline_through_stage7(monkeypatch, verdict: NLIVerdict):
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.extract_entities", lambda text: [ExtractedEntity(text="x", label="GPE")]
    )
    monkeypatch.setattr("app.db.repository.save_claim", _async_noop)

    async def fake_search(claim_text, *, entities=None, sources=None):
        return [EvidenceDocument(source="wikipedia", title="t", url="https://example.com/1", snippet="s")]

    monkeypatch.setattr("app.pipeline.stage3_evidence_search.search_all_sources", fake_search)
    monkeypatch.setattr(
        "app.pipeline.stage3_evidence_search.enrich_entities_with_wikidata", lambda entities: _async_return(entities)
    )
    monkeypatch.setattr("app.pipeline.stage4_bm25_retrieval.rank_by_bm25", lambda claim_text, docs: _to_retrieved(docs))
    monkeypatch.setattr(
        "app.pipeline.stage5_semantic_matching.rank_by_semantic_similarity",
        lambda claim_text, docs: [_to_ranked(d) for d in docs],
    )
    monkeypatch.setattr(
        "app.pipeline.stage6_reranking.rerank", lambda claim_text, docs, top_k=5: [_to_reranked(d) for d in docs]
    )
    monkeypatch.setattr("app.pipeline.stage7_nli_verification.verify_claim", lambda claim_text, docs: [verdict])
    monkeypatch.setattr("app.db.repository.save_evidence_items", _async_noop)
    monkeypatch.setattr("app.db.repository.save_trust_breakdown", _async_noop)
    monkeypatch.setattr("app.pipeline.stage9_explanation.generate_explanation", lambda result: "an explanation")


async def test_evidence_claim_resolution_disabled_skips_stage7b(monkeypatch):
    _stub_pipeline_through_stage7(monkeypatch, _fake_verdict())

    called = []
    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.resolve_ambiguous_verdicts",
        lambda claim_text, verdicts, **kwargs: called.append(1),
    )
    monkeypatch.setattr(
        "app.pipeline.orchestrator.get_settings",
        lambda: type("S", (), {"evidence_claim_resolution_enabled": False})(),
    )

    await orchestrator._process_claim("Some claim", 0, session=None, run_id=uuid.uuid4())

    assert called == []


async def test_evidence_claim_resolution_failure_falls_back_to_first_pass_verdicts(monkeypatch):
    _stub_pipeline_through_stage7(monkeypatch, _fake_verdict())

    async def raise_error(claim_text, verdicts, **kwargs):
        raise RuntimeError("stage7b blew up")

    monkeypatch.setattr(
        "app.pipeline.stage7b_evidence_claim_resolution.resolve_ambiguous_verdicts", raise_error
    )
    monkeypatch.setattr(
        "app.pipeline.orchestrator.get_settings",
        lambda: type("S", (), {"evidence_claim_resolution_enabled": True})(),
    )

    result = await orchestrator._process_claim("Some claim", 0, session=None, run_id=uuid.uuid4())

    # a stage7b crash costs the claim its LLM-refined verdicts, not the claim itself
    assert result.trust_score > 50  # first-pass entailment verdict still scored normally


async def _async_noop(*args, **kwargs):
    return None


async def _async_return(value):
    return value


def _to_retrieved(docs):
    from app.schemas.evidence import RetrievedEvidence

    return [RetrievedEvidence(**d.model_dump(), bm25_score=1.0) for d in docs]


def _to_ranked(doc):
    from app.schemas.ranking import RankedEvidence

    return RankedEvidence(**doc.model_dump(), semantic_similarity_score=1.0)


def _to_reranked(doc):
    from app.schemas.ranking import RerankedEvidence

    return RerankedEvidence(**doc.model_dump(), cross_encoder_score=1.0)
