"""Generate pyveil's privacy-safe Proof-of-Compatibility Receipt.

The receipt is a public evidence artifact for the synthetic protection-surface
set. It records, per surface, which entity types were redacted (counts only),
whether the fixture met its gate, and a SHA-256 of the redacted (placeholder)
output. It deliberately excludes raw prompts, PII, and secrets.

Before writing, a pre-publish scan asserts that no known synthetic sensitive
value or the fixture secret appears anywhere in the receipt. A failing run still
produces a receipt that names the failing gates, so regressions are auditable.

Usage::

    python scripts/compatibility_receipt.py --check   # verify + scan, no write
    python scripts/compatibility_receipt.py --write   # (re)write receipt.json/md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyveil import __version__ as pyveil_version  # noqa: E402
from scripts.compat_harness import (  # noqa: E402
    COMPAT_DIR,
    FixtureOutcome,
    load_fixtures,
    run_all,
)

RECEIPT_JSON = COMPAT_DIR / "receipt.json"
RECEIPT_MD = COMPAT_DIR / "receipt.md"
SCHEMA_VERSION = 1


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _environment() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
    }


def build_receipt(outcomes: list[FixtureOutcome]) -> dict[str, Any]:
    surfaces: dict[str, list[dict[str, Any]]] = {}
    totals: Counter[str] = Counter()
    passed = 0
    for outcome in outcomes:
        totals.update(outcome.counts_by_type)
        if outcome.passed:
            passed += 1
        surfaces.setdefault(outcome.channel, []).append(
            {
                "fixture_id": outcome.fixture_id,
                "category": outcome.category,
                "blocked": outcome.blocked,
                "redaction_counts": dict(sorted(outcome.counts_by_type.items())),
                "output_sha256": outcome.output_sha256,
                "gate": "pass" if outcome.passed else "fail",
                "reasons": list(outcome.failures),
            }
        )
    failed = len(outcomes) - passed
    return {
        "schema_version": SCHEMA_VERSION,
        "project": "pyveil",
        "pyveil_version": pyveil_version,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git_commit(),
        "environment": _environment(),
        "gate": "pass" if failed == 0 else "fail",
        "totals": {
            "fixtures": len(outcomes),
            "passed": passed,
            "failed": failed,
            "surfaces": len(surfaces),
        },
        "redaction_summary": dict(sorted(totals.items())),
        "surfaces": {
            channel: sorted(entries, key=lambda item: item["fixture_id"])
            for channel, entries in sorted(surfaces.items())
        },
        "privacy_note": (
            "Redaction counts and output hashes only. No raw prompt, PII, or "
            "secret is included. Placeholders are scoped HMAC digests."
        ),
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    totals = receipt["totals"]
    lines = [
        "# pyveil Proof-of-Compatibility Receipt",
        "",
        "Privacy-safe evidence for the synthetic protection-surface set. Counts "
        "and hashes only; no raw prompt, PII, or secret.",
        "",
        f"- Generated: `{receipt['generated_at']}`",
        f"- pyveil: `{receipt['pyveil_version']}`",
        f"- Commit: `{receipt['git_commit'] or 'unknown'}`",
        f"- Environment: {receipt['environment']['implementation']} "
        f"{receipt['environment']['python_version']} on {receipt['environment']['system']}",
        f"- Gate: **{receipt['gate']}** "
        f"({totals['passed']}/{totals['fixtures']} fixtures across "
        f"{totals['surfaces']} surfaces)",
        "",
        "## Redaction summary",
        "",
        "| Entity type | Redacted count |",
        "| --- | --- |",
    ]
    for entity_type, count in receipt["redaction_summary"].items():
        lines.append(f"| `{entity_type}` | {count} |")
    lines.extend(["", "## Surfaces", "", "| Channel | Fixture | Category | Gate | Redactions | Output SHA-256 |", "| --- | --- | --- | --- | --- | --- |"])
    for channel, entries in receipt["surfaces"].items():
        for entry in entries:
            counts = ", ".join(f"{k}={v}" for k, v in entry["redaction_counts"].items()) or "-"
            digest = entry["output_sha256"][:16] + "…" if entry["output_sha256"] else "blocked"
            lines.append(
                f"| `{channel}` | `{entry['fixture_id']}` | {entry['category']} "
                f"| {entry['gate']} | {counts} | `{digest}` |"
            )
    lines.append("")
    return "\n".join(lines)


def forbidden_tokens(fixtures: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    secret = str(fixtures.get("secret", ""))
    if secret:
        tokens.add(secret)
    for fixture in fixtures["fixtures"]:
        for value in fixture.get("expect_absent", []):
            if isinstance(value, str) and value:
                tokens.add(value)
    return sorted(tokens)


def scan_for_leaks(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token in text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify gates and scan; do not write")
    parser.add_argument("--write", action="store_true", help="Write receipt.json and receipt.md")
    args = parser.parse_args()

    fixtures = load_fixtures()
    outcomes = run_all(fixtures)
    receipt = build_receipt(outcomes)
    receipt_json = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    receipt_md = render_markdown(receipt)

    tokens = forbidden_tokens(fixtures)
    leaks = scan_for_leaks(receipt_json + "\n" + receipt_md, tokens)
    if leaks:
        print(f"receipt aborted: {len(leaks)} synthetic sensitive value(s) leaked into the receipt")
        return 2

    if args.write:
        RECEIPT_JSON.write_text(receipt_json + "\n", encoding="utf-8")
        RECEIPT_MD.write_text(receipt_md, encoding="utf-8")
        print(f"receipt written: {RECEIPT_JSON.name}, {RECEIPT_MD.name}")

    totals = receipt["totals"]
    print(
        f"receipt gate: {receipt['gate']} "
        f"({totals['passed']}/{totals['fixtures']} fixtures, {totals['surfaces']} surfaces); "
        f"pre-publish scan clean ({len(tokens)} tokens checked)"
    )
    return 0 if receipt["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
