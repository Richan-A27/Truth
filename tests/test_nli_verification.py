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
