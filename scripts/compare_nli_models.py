"""Diagnostic A/B comparison of the two NLI backends (see
app.ml.model_registry.NLI_MODEL_VARIANTS) on the fixed set of known failure
classes in tests/fixtures/nli_diagnostic_cases.json.

Runs each (evidence, claim) pair directly through both models' raw predict()
call - bypassing stage 7's heuristics (relevance floor, hedge detection,
sentence selection) on purpose, so this measures what the MODEL ITSELF gets
right or wrong, not what the surrounding pipeline compensates for.
"""

import json
import time
from pathlib import Path

import numpy as np

from app.ml.model_registry import get_nli_labels, get_nli_model

FIXTURES = json.loads((Path(__file__).parent.parent / "tests" / "fixtures" / "nli_diagnostic_cases.json").read_text())


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def _score_all(variant: str) -> tuple[list[dict], float]:
    model = get_nli_model(variant)
    labels = get_nli_labels(variant)
    pairs = [(case["evidence"], case["claim"]) for case in FIXTURES]

    start = time.perf_counter()
    logits = model.predict(pairs)
    elapsed = time.perf_counter() - start

    probs = _softmax(np.asarray(logits))
    results = []
    for case, prob_row in zip(FIXTURES, probs):
        prob_dict = {label: float(prob_row[i]) for i, label in enumerate(labels)}
        predicted = max(prob_dict, key=prob_dict.get)
        results.append({**case, "predicted_label": predicted, "probs": prob_dict})
    return results, elapsed


def main() -> None:
    print(f"Loading both NLI models ({len(FIXTURES)} diagnostic cases)...\n")
    current_results, current_time = _score_all("current")
    fv_results, fv_time = _score_all("fact_verification")

    current_correct = fv_correct = 0
    print(f"{'category':32s} {'expected':13s} {'current':22s} {'fact_verification':22s} agree?")
    print("-" * 110)
    for c, f in zip(current_results, fv_results):
        c_ok = c["predicted_label"] == c["expected_label"]
        f_ok = f["predicted_label"] == f["expected_label"]
        current_correct += c_ok
        fv_correct += f_ok
        c_str = f"{c['predicted_label']} ({c['probs'][c['predicted_label']]:.2f}){'  OK' if c_ok else '  X'}"
        f_str = f"{f['predicted_label']} ({f['probs'][f['predicted_label']]:.2f}){'  OK' if f_ok else '  X'}"
        print(f"{c['category']:32s} {c['expected_label']:13s} {c_str:22s} {f_str:22s} {'same' if c['predicted_label']==f['predicted_label'] else 'DIFF'}")
        print(f"   claim: {c['claim'][:90]}")
        print(f"   evidence: {c['evidence'][:90]}")
        print(f"   current probs: {c['probs']}")
        print(f"   fact_verification probs: {f['probs']}")
        print()

    print("=" * 110)
    print(f"current model:            {current_correct}/{len(FIXTURES)} correct, {current_time*1000:.1f}ms for {len(FIXTURES)} pairs")
    print(f"fact_verification model:  {fv_correct}/{len(FIXTURES)} correct, {fv_time*1000:.1f}ms for {len(FIXTURES)} pairs")

    print("\nBy category:")
    categories = sorted({c["category"] for c in FIXTURES})
    for cat in categories:
        c_cat = [r for r in current_results if r["category"] == cat]
        f_cat = [r for r in fv_results if r["category"] == cat]
        c_ok = sum(r["predicted_label"] == r["expected_label"] for r in c_cat)
        f_ok = sum(r["predicted_label"] == r["expected_label"] for r in f_cat)
        print(f"  {cat:40s} current: {c_ok}/{len(c_cat)}   fact_verification: {f_ok}/{len(f_cat)}")


if __name__ == "__main__":
    main()
