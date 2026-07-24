"""Shared harness for pyveil's synthetic protection-surface compatibility set.

This module is the single execution path for:

- ``tests/test_compatibility_surfaces.py`` (assertions)
- ``scripts/validate_compatibility.py`` (static manifest/fixture validation)
- ``scripts/compatibility_receipt.py`` (privacy-safe evidence receipt)

It runs synthetic fixtures through pyveil and evaluates each one against its
expected redaction, structure-preservation, and fail-closed behavior. It never
returns raw redacted payloads or raw sensitive values to callers; only entity
counts, boolean gate outcomes, and a hash of the redacted (placeholder) output
leave this module.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPAT_DIR = REPO_ROOT / "compatibility"
FIXTURES_PATH = COMPAT_DIR / "fixtures.json"
MANIFEST_PATH = COMPAT_DIR / "manifest.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyveil import BlockedSensitiveData, Veil  # noqa: E402
from pyveil.constants import Channel  # noqa: E402

KNOWN_CATEGORIES = frozenset(
    {"basic", "nested", "unicode", "broken_json", "false_positive", "fail_closed"}
)
KNOWN_MODES = frozenset({"text", "data"})
CHANNEL_VALUES = frozenset(channel.value for channel in Channel)


@dataclass
class FixtureOutcome:
    """Privacy-safe result of running a single fixture.

    No raw input or raw sensitive value is stored here. ``output_sha256`` is a
    hash of the redacted (placeholder) output, which contains no raw secrets.
    """

    fixture_id: str
    channel: str
    category: str
    blocked: bool
    counts_by_type: dict[str, int]
    output_sha256: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def load_fixtures(path: Path = FIXTURES_PATH) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("fixtures"), list):
        raise ValueError("unsupported compatibility fixture file")
    return payload


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("surfaces"), list):
        raise ValueError("unsupported compatibility manifest file")
    return payload


def build_veil(fixtures: dict[str, Any]) -> Veil:
    secret = str(fixtures.get("secret", "synthetic-compatibility-secret")).encode("utf-8")
    scope = str(fixtures.get("scope", "compatibility/v1"))
    return Veil.high(secret=secret, scope=scope)


def _serialize(data: Any) -> str:
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _same_shape(original: Any, redacted: Any) -> bool:
    if isinstance(original, dict):
        if not isinstance(redacted, dict) or set(original) != set(redacted):
            return False
        return all(_same_shape(original[key], redacted[key]) for key in original)
    if isinstance(original, (list, tuple)):
        if not isinstance(redacted, type(original)) or len(original) != len(redacted):
            return False
        return all(_same_shape(a, b) for a, b in zip(original, redacted))
    if isinstance(original, str):
        return isinstance(redacted, str)
    return bool(original == redacted)


def run_fixture(veil: Veil, fixture: dict[str, Any]) -> FixtureOutcome:
    """Run one fixture and evaluate it against its expectations."""

    fixture_id = str(fixture["id"])
    channel = str(fixture["channel"])
    category = str(fixture["category"])
    mode = str(fixture["mode"])
    expect_blocked = bool(fixture.get("expect_blocked", False))
    failures: list[str] = []

    try:
        if mode == "text":
            result = veil.redact_text(fixture["input"], channel=channel)
        else:
            result = veil.redact_data(fixture["input"], channel=channel)
    except BlockedSensitiveData as exc:
        counts: dict[str, int] = {}
        for finding in exc.findings:
            counts[finding.type] = counts.get(finding.type, 0) + 1
        if not expect_blocked:
            failures.append("unexpected fail-closed block")
        expected = sorted(fixture.get("expect_entities", []))
        if sorted(counts) != expected:
            failures.append("blocked entity types differ from expected")
        if any(finding.raw is not None for finding in exc.findings):
            failures.append("blocked finding stored a raw value")
        return FixtureOutcome(
            fixture_id=fixture_id,
            channel=channel,
            category=category,
            blocked=True,
            counts_by_type=counts,
            output_sha256="",
            failures=failures,
        )

    if expect_blocked:
        failures.append("expected fail-closed block but redaction returned")

    serialized = _serialize(result.data)
    counts = dict(result.stats.counts_by_type)

    if sorted(counts) != sorted(fixture.get("expect_entities", [])):
        failures.append("detected entity types differ from expected")

    for value in fixture.get("expect_absent", []):
        if value in serialized:
            failures.append("expected-absent sensitive value survived redaction")

    for value in fixture.get("expect_preserved", []):
        if value not in serialized:
            failures.append("expected-preserved non-sensitive value was dropped")

    if any(finding.raw is not None for finding in result.findings):
        failures.append("finding stored a raw value")

    if category == "false_positive" and result.data != fixture["input"]:
        failures.append("false-positive fixture changed a non-sensitive payload")

    if category == "broken_json" and not isinstance(result.data, str):
        failures.append("broken-json fixture did not fall back to text")

    if (
        mode == "data"
        and category not in ("broken_json", "fail_closed")
        and not _same_shape(fixture["input"], result.data)
    ):
        failures.append("structured redaction did not preserve payload shape")

    output_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return FixtureOutcome(
        fixture_id=fixture_id,
        channel=channel,
        category=category,
        blocked=False,
        counts_by_type=counts,
        output_sha256=output_sha256,
        failures=failures,
    )


def run_all(fixtures: dict[str, Any] | None = None) -> list[FixtureOutcome]:
    payload = fixtures if fixtures is not None else load_fixtures()
    veil = build_veil(payload)
    return [run_fixture(veil, fixture) for fixture in payload["fixtures"]]
