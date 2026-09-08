"""Diagnostic comparison of the Ollama-prompted stage5-7 replacement
(app.clients.ollama_client.verify_evidence_batch) against the existing
cross-encoder NLI stage, on the same fixed failure-class cases in
tests/fixtures/nli_diagnostic_cases.json used by compare_nli_models.py.

Cases are grouped by claim and sent to Ollama in one batched call per claim
- the same one-call-per-claim shape the real pipeline would use, not one
call per (claim, evidence) pair, which the ~7-8s/call local latency would
make far too slow (see verify_evidence_batch's docstring).

Unlike compare_nli_models.py this hits a live Ollama server and takes
minutes, not milliseconds - make sure `ollama serve` is running with
settings.ollama_model pulled first.
"""

import json
import time
from collections import defaultdict
from pathlib import Path

from app.clients import ollama_client
from app.config import get_settings

FIXTURES = json.loads((Path(__file__).parent.parent / "tests" / "fixtures" / "nli_diagnostic_cases.json").read_text())


def _grouped_by_claim() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in FIXTURES:
        groups[case["claim"]].append(case)
    return groups


def main() -> None:
    groups = _grouped_by_claim()
    print(
        f"Running {len(FIXTURES)} diagnostic cases across {len(groups)} claims through Ollama "
        f"({get_settings().ollama_model}) - this will take a few minutes...\n"
    )

    results = []
    start = time.perf_counter()
    for claim_text, cases in groups.items():
        verdicts = ollama_client.verify_evidence_batch(claim_text, [c["evidence"] for c in cases])
        for case, verdict in zip(cases, verdicts):
            results.append({**case, "predicted_label": verdict["label"], "confidence": verdict["confidence"]})
    elapsed = time.perf_counter() - start

    correct = 0
    print(f"{'category':32s} {'expected':13s} {'llm predicted':22s} ok?")
    print("-" * 90)
    for r in results:
        ok = r["predicted_label"] == r["expected_label"]
        correct += ok
        status = "OK" if ok else "X"
        predicted_str = f"{r['predicted_label']} ({r['confidence']:.2f})"
        print(f"{r['category']:32s} {r['expected_label']:13s} {predicted_str:22s} {status}")
        print(f"   claim: {r['claim'][:90]}")
        print(f"   evidence: {r['evidence'][:90]}")
        print()

    print("=" * 90)
    print(
        f"llm (ollama):  {correct}/{len(results)} correct, {elapsed:.1f}s total for {len(groups)} calls "
        f"({elapsed / len(groups):.1f}s/call avg)"
    )

    print("\nBy category:")
    for cat in sorted({r["category"] for r in results}):
        cat_results = [r for r in results if r["category"] == cat]
        ok = sum(r["predicted_label"] == r["expected_label"] for r in cat_results)
        print(f"  {cat:40s} llm: {ok}/{len(cat_results)}")


if __name__ == "__main__":
    main()
