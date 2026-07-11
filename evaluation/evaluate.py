"""Run pyveil's synthetic built-in detector regression evaluation."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from pyveil import Veil

CORPUS_PATH = Path(__file__).with_name("corpus.json")


def load_cases(path: Path = CORPUS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("cases"), list):
        raise ValueError("unsupported evaluation corpus")
    return payload["cases"]


def evaluate(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    veil = Veil.high(secret=b"synthetic-evaluation-only", scope="evaluation/v1")
    true_positive = 0
    false_positive = 0
    false_negative = 0
    positive_cases = 0
    mismatches: list[dict[str, Any]] = []
    started = time.perf_counter()

    for case in cases:
        expected = Counter(case["expected"])
        if expected:
            positive_cases += 1
        result = veil.redact_text(case["text"], channel="prompt.input")
        actual = Counter(result.stats.counts_by_type)
        true_positive += sum((expected & actual).values())
        false_positive += sum((actual - expected).values())
        false_negative += sum((expected - actual).values())

        leaked = [value for value in case.get("sensitive", []) if value in result.text]
        raw_findings = [finding.type for finding in result.findings if finding.raw is not None]
        changed_negative = not expected and result.text != case["text"]
        if expected != actual or leaked or raw_findings or changed_negative:
            mismatches.append(
                {
                    "id": case["id"],
                    "expected": dict(expected),
                    "actual": dict(actual),
                    "leaked_values": len(leaked),
                    "raw_findings": raw_findings,
                    "changed_negative": changed_negative,
                }
            )

    elapsed = time.perf_counter() - started
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    return {
        "corpus": "synthetic built-in detector regression corpus",
        "cases": len(cases),
        "positive_cases": positive_cases,
        "negative_cases": len(cases) - positive_cases,
        "expected_findings": true_positive + false_negative,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": true_positive / precision_denominator if precision_denominator else 1.0,
        "recall": true_positive / recall_denominator if recall_denominator else 1.0,
        "mismatches": mismatches,
        "elapsed_ms": round(elapsed * 1000, 3),
    }


def benchmark(iterations: int = 200) -> dict[str, Any]:
    veil = Veil.high(secret=b"synthetic-benchmark-only", scope="evaluation/benchmark")
    text = (
        "Customer alice@example.com called +14155550199. "
        "api_key=sk-proj-DEMO_ONLY_000000000000000000 "
    ) * 100
    timings = []
    for _ in range(iterations):
        started = time.perf_counter()
        veil.redact_text(text, channel="prompt.input")
        timings.append(time.perf_counter() - started)
    median = statistics.median(timings)
    return {
        "input_chars": len(text),
        "iterations": iterations,
        "median_ms": round(median * 1000, 3),
        "median_mib_per_second": round((len(text) / (1024 * 1024)) / median, 3),
        "note": "Machine-dependent diagnostic; no latency SLA.",
    }


def print_human(result: dict[str, Any]) -> None:
    print("pyveil synthetic detector regression evaluation")
    print(
        f"cases: {result['cases']} ({result['positive_cases']} positive, "
        f"{result['negative_cases']} negative)"
    )
    print(f"expected findings: {result['expected_findings']}")
    print(f"precision: {result['precision']:.3f}")
    print(f"recall: {result['recall']:.3f}")
    print(f"false positives: {result['false_positive']}")
    print(f"false negatives: {result['false_negative']}")
    print(f"mismatches: {len(result['mismatches'])}")
    if "benchmark" in result:
        measured = result["benchmark"]
        print(
            "benchmark median: "
            f"{measured['median_ms']:.3f} ms for {measured['input_chars']} chars "
            f"({measured['median_mib_per_second']:.3f} MiB/s)"
        )
    print("scope: synthetic supported-shape regression only; not real-world PII recall")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit non-zero on any mismatch")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--benchmark", action="store_true", help="Run a local latency diagnostic")
    args = parser.parse_args()

    result = evaluate(load_cases())
    if args.benchmark:
        result["benchmark"] = benchmark()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(result)
        for mismatch in result["mismatches"]:
            print("mismatch: " + json.dumps(mismatch, sort_keys=True))
    return 1 if args.check and result["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
