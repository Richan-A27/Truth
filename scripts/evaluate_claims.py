"""Batch-evaluate the verification pipeline against labelled claims.

Runs each claim through POST /verify/claim (no LLM involved) and reports
accuracy against the expected verdict, so pipeline changes can be compared
run over run.

Usage:
    python scripts/evaluate_claims.py [--url http://localhost:8010]
"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx

DEFAULT_URL = "http://localhost:8010"
CASES_PATH = Path(__file__).parent / "eval_claims.json"


async def evaluate_one(client: httpx.AsyncClient, base_url: str, case: dict) -> dict:
    try:
        resp = await client.post(
            f"{base_url}/verify/claim", json={"claim": case["claim"]}, timeout=120.0
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 - report the failure, keep evaluating
        return {**case, "error": str(exc), "verdict": "ERROR", "score": None, "correct": False}

    verdict = body["verdict_label"]
    claim_detail = body["claims"][0] if body["claims"] else {}
    return {
        **case,
        "verdict": verdict,
        "score": body["trust_score"],
        "correct": verdict in case["acceptable"],
        "supporting": len(claim_detail.get("supporting_evidence", [])),
        "contradicting": len(claim_detail.get("contradicting_evidence", [])),
        "neutral": claim_detail.get("breakdown", {}).get("neutral_count", 0),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text())

    results = []
    async with httpx.AsyncClient() as client:
        # sequential: the dev server holds one copy of each model
        for case in cases:
            result = await evaluate_one(client, args.url, case)
            results.append(result)
            mark = "PASS" if result["correct"] else "FAIL"
            print(
                f"{mark}  {result['score'] if result['score'] is not None else '--':>4}  "
                f"{result['verdict']:<13} (want {'/'.join(case['acceptable'])})  "
                f"S{result.get('supporting', 0)} C{result.get('contradicting', 0)} "
                f"N{result.get('neutral', 0)}  {case['claim'][:60]}"
            )

    passed = sum(1 for r in results if r["correct"])
    print(f"\n{passed}/{len(results)} correct ({100 * passed / len(results):.0f}%)")

    failures = [r for r in results if not r["correct"]]
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  - [{r['label']}] {r['claim']}")
            print(f"      got {r['verdict']} ({r['score']}), expected {'/'.join(r['acceptable'])}")
            if r.get("error"):
                print(f"      error: {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
