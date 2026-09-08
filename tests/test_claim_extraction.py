import os

import pytest

from app.pipeline import stage2_claim_extraction


def _stub_llm_client(monkeypatch, extract_claims_fn):
    """Patch the dispatcher itself, not a concrete backend module - which
    backend get_llm_client() picks depends on the local LLM_BACKEND setting,
    and patching e.g. gemini_client.extract_claims directly silently no-ops
    (and the test passes against a totally different code path) when
    LLM_BACKEND=ollama is set locally."""
    stub = type("StubClient", (), {"extract_claims": staticmethod(extract_claims_fn)})
    monkeypatch.setattr("app.pipeline.stage2_claim_extraction.get_llm_client", lambda: stub)


def test_extract_claims_parses_gemini_output(monkeypatch):
    _stub_llm_client(monkeypatch, lambda content: ["The sky is blue.", "Water boils at 100C at sea level."])

    claims = stage2_claim_extraction.extract_claims("some article text")

    assert [c.text for c in claims] == ["The sky is blue.", "Water boils at 100C at sea level."]
    assert [c.order for c in claims] == [0, 1]


def test_extract_claims_handles_empty_list(monkeypatch):
    _stub_llm_client(monkeypatch, lambda content: [])
    assert stage2_claim_extraction.extract_claims("no claims here") == []


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="requires GEMINI_API_KEY")
def test_live_gemini_claim_extraction():
    claims = stage2_claim_extraction.extract_claims(
        "The Eiffel Tower was completed in 1889 and is located in Paris."
    )
    assert len(claims) >= 1
