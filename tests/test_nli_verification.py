import json
from pathlib import Path

import pytest

from app.ml.model_registry import get_nli_labels, get_nli_model
from app.pipeline.stage7_nli_verification import _softmax
import numpy as np

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "nli_pairs.json").read_text())

# No "neutral" case is included here: cross-encoder/nli-deberta-v3-base was
# found (during manual testing, 9/9 unrelated pairs checked) to reliably
# mislabel topically-unrelated sentence pairs as "contradiction" rather than
# "neutral". The pipeline does not rely on the raw model for that
# distinction - stage7_nli_verification.py forces evidence the reranker
# scored as irrelevant to "neutral" regardless of the model's own label; see
# tests/test_nli_relevance_floor.py for that behavior.


@pytest.mark.integration
@pytest.mark.parametrize("case", FIXTURES, ids=[c["hypothesis"][:30] for c in FIXTURES])
def test_known_nli_pairs_classify_correctly(case):
    model = get_nli_model()
    logits = model.predict([(case["premise"], case["hypothesis"])])
    probs = _softmax(np.asarray(logits))

    label = get_nli_labels()[int(np.argmax(probs[0]))]
    assert label == case["expected_label"]


def test_numbers_within_rounding_agree():
    from app.pipeline.stage7_nli_verification import _numbers_agree

    claim = "The speed of light is approximately 300,000 kilometers per second."
    assert _numbers_agree(claim, "Light travels at about 299,792 km/s in a vacuum.")
    assert not _numbers_agree(claim, "Rømer estimated a speed of about 220,000 km/s.")
    assert _numbers_agree("The human body has 206 bones.", "An adult skeleton has 206 bones.")
    assert not _numbers_agree("The human body has 206 bones.", "Humans have 213 bones.")


def test_year_only_claims_never_count_as_number_agreement():
    from app.pipeline.stage7_nli_verification import _numbers_agree

    # date agreement says nothing about the rest of the claim (here: the city)
    assert not _numbers_agree("The Eiffel Tower was built in Berlin in 1889.", "It was built in Paris in 1889.")


def test_number_agreement_overrides_nli_contradiction(monkeypatch):
    import numpy as np

    from app.pipeline import stage7_nli_verification as s7
    from app.schemas.ranking import RerankedEvidence

    class FakeNLI:
        def predict(self, pairs, batch_size=32):
            # contradiction, entailment, neutral - confident contradiction
            return np.array([[5.0, -5.0, -5.0]] * len(pairs))

    monkeypatch.setattr(s7, "get_nli_model", lambda variant=None: FakeNLI())
    monkeypatch.setattr(s7, "get_nli_labels", lambda variant=None: ["contradiction", "entailment", "neutral"])
    doc = RerankedEvidence(
        source="wikipedia",
        title="Speed of light",
        url="https://en.wikipedia.org/wiki/Speed_of_light",
        snippet="Light in a vacuum travels at about 299,792 kilometres per second.",
        cross_encoder_score=5.0,
    )

    [verdict] = s7.verify_claim("The speed of light is approximately 300,000 kilometers per second.", [doc])

    assert verdict.label == "neutral"
