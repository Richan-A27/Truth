import pytest

from app.clients.gemini_client import _normalize_evidence_claim as gemini_normalize
from app.clients.ollama_client import _normalize_evidence_claim as ollama_normalize


@pytest.mark.parametrize("normalize", [gemini_normalize, ollama_normalize])
class TestNormalizeEvidenceClaim:
    def test_strips_surrounding_quotes_and_whitespace(self, normalize):
        assert normalize('  "Bats have functional eyesight."  ') == "Bats have functional eyesight."

    def test_returns_empty_for_undetermined_sentinel(self, normalize):
        assert normalize("UNDETERMINED") == ""
        assert normalize("undetermined") == ""

    def test_returns_empty_for_other_sentinels(self, normalize):
        assert normalize("N/A") == ""
        assert normalize("None") == ""
        assert normalize("unknown") == ""

    def test_returns_empty_for_empty_or_none_input(self, normalize):
        assert normalize("") == ""
        assert normalize(None) == ""

    def test_returns_empty_if_a_question_mark_survived(self, normalize):
        assert normalize("Was Einstein really bad at math?") == ""

    def test_passes_through_a_clean_sentence(self, normalize):
        text = "Einstein was in fact a strong mathematics student; the failing-math story is a myth."
        assert normalize(text) == text
