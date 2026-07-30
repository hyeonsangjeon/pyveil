"""Deterministic, offline replay of pyveil's six agent privacy boundaries.

The replay uses built-in synthetic values and the public ``Veil`` API. Its
report contains only identifiers, counts, booleans, and hashes. Raw fixture
inputs and redacted payloads are never emitted.

The report also carries a resume-safety pass that re-crosses each boundary with
already-redacted state, modelling a resumed checkpoint. It proves the raw value
never returns and records whether re-redaction is a byte-stable fixed point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .constants import Channel
from .core import Veil
from .exceptions import BlockedSensitiveData

REPLAY_SCHEMA_VERSION = 1
_REPLAY_SECRET = b"pyveil-synthetic-privacy-replay"
_REPLAY_SCOPE = "privacy-boundary-replay/v1"

_SYNTHETIC_EMAIL = "replay.user@example.com"
_SYNTHETIC_API_KEY = "sk-proj-EXAMPLEabcdefghijklmnopqrstuvwx"
_SYNTHETIC_QUERY_TOKEN = "EXAMPLEsecrettoken12345"
_SYNTHETIC_JWT = (
    "eyJhbGciOiJIUzI1NiJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)
_SYNTHETIC_BEARER = "abcdefgh12345678ZZ"
_BENIGN_CASE_ID = "CASE-7421"


@dataclass(frozen=True)
class ReplayCase:
    """One synthetic boundary scenario.

    ``sensitive_markers`` and ``payload`` are used only during evaluation and
    are deliberately absent from ``ReplayOutcome``.
    """

    case_id: str
    boundary: str
    channel: str
    mode: str
    payload: Any
    expected_entities: tuple[str, ...]
    sensitive_markers: tuple[str, ...]
    benign_markers: tuple[str, ...]
    expect_blocked: bool = False


@dataclass(frozen=True)
class ReplayOutcome:
    """Privacy-safe evidence for one replay case."""

    case_id: str
    boundary: str
    channel: str
    blocked: bool
    input_sha256: str
    output_sha256: str
    finding_count: int
    redacted_count: int
    leak_count: int
    benign_preserved: bool
    structure_preserved: bool
    counts_by_type: dict[str, int]
    failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        """Return the stable, raw-value-free representation used in reports."""

        return {
            "case_id": self.case_id,
            "boundary": self.boundary,
            "channel": self.channel,
            "blocked": self.blocked,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "finding_count": self.finding_count,
            "redacted_count": self.redacted_count,
            "leak_count": self.leak_count,
            "benign_preserved": self.benign_preserved,
            "structure_preserved": self.structure_preserved,
            "counts_by_type": dict(sorted(self.counts_by_type.items())),
            "gate": "pass" if self.passed else "fail",
            "reasons": list(self.failures),
        }


@dataclass(frozen=True)
class ResumeOutcome:
    """Privacy-safe evidence that a boundary is safe to persist and resume.

    Produced by re-applying redaction to an already-redacted payload, which
    models a resumed checkpoint that re-crosses the same boundary. It proves
    the raw value never returns and records whether re-redaction is a byte
    stable fixed point.
    """

    case_id: str
    boundary: str
    channel: str
    leak_count: int
    resume_finding_count: int
    byte_stable: bool
    first_output_sha256: str
    resumed_output_sha256: str
    failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        """Return the stable, raw-value-free representation used in reports."""

        return {
            "case_id": self.case_id,
            "boundary": self.boundary,
            "channel": self.channel,
            "leak_count": self.leak_count,
            "resume_finding_count": self.resume_finding_count,
            "byte_stable": self.byte_stable,
            "first_output_sha256": self.first_output_sha256,
            "resumed_output_sha256": self.resumed_output_sha256,
            "gate": "pass" if self.passed else "fail",
            "reasons": list(self.failures),
        }


def default_replay_cases() -> tuple[ReplayCase, ...]:
    """Return the built-in prompt, tool, MCP, memory, log, and trace cases."""

    return (
        ReplayCase(
            case_id="prompt-before-model",
            boundary="prompt",
            channel=Channel.PROMPT_INPUT.value,
            mode="text",
            payload=(
                f"Draft {_BENIGN_CASE_ID} for {_SYNTHETIC_EMAIL} using "
                f"{_SYNTHETIC_API_KEY}."
            ),
            expected_entities=("API_KEY", "EMAIL"),
            sensitive_markers=(_SYNTHETIC_EMAIL, _SYNTHETIC_API_KEY),
            benign_markers=("Draft", _BENIGN_CASE_ID),
        ),
        ReplayCase(
            case_id="tool-call-before-execution",
            boundary="tool_call",
            channel=Channel.TOOL_CALL_ARGUMENTS.value,
            mode="data",
            payload={
                "tool": "lookup_customer",
                "arguments": {
                    "email": _SYNTHETIC_EMAIL,
                    "case_id": _BENIGN_CASE_ID,
                    "limit": 3,
                },
            },
            expected_entities=("EMAIL",),
            sensitive_markers=(_SYNTHETIC_EMAIL,),
            benign_markers=("lookup_customer", _BENIGN_CASE_ID),
        ),
        ReplayCase(
            case_id="mcp-resource-before-context",
            boundary="mcp",
            channel=Channel.MCP_RESOURCE_CONTENT.value,
            mode="data",
            payload={
                "uri": f"file://synthetic/{_BENIGN_CASE_ID}.txt",
                "text": (
                    f"Contact {_SYNTHETIC_EMAIL} via "
                    "https://api.example.com/cb?"
                    f"access_token={_SYNTHETIC_QUERY_TOKEN}"
                ),
                "mime_type": "text/plain",
            },
            expected_entities=("EMAIL", "URL_QUERY_SECRET"),
            sensitive_markers=(_SYNTHETIC_EMAIL, _SYNTHETIC_QUERY_TOKEN),
            benign_markers=(_BENIGN_CASE_ID, "text/plain"),
        ),
        ReplayCase(
            case_id="memory-before-persistence",
            boundary="memory",
            channel=Channel.MEMORY_WRITE.value,
            mode="data",
            payload={
                "note": (
                    f"Remember {_BENIGN_CASE_ID} owner {_SYNTHETIC_EMAIL}; "
                    f"session {_SYNTHETIC_JWT}"
                ),
                "kind": "support",
            },
            expected_entities=("EMAIL", "JWT"),
            sensitive_markers=(_SYNTHETIC_EMAIL, _SYNTHETIC_JWT),
            benign_markers=(_BENIGN_CASE_ID, "support"),
        ),
        ReplayCase(
            case_id="log-before-handler",
            boundary="log",
            channel=Channel.LOG_RECORD.value,
            mode="text",
            payload=(
                f"INFO {_BENIGN_CASE_ID} user {_SYNTHETIC_EMAIL} failed with "
                f"Authorization: Bearer {_SYNTHETIC_BEARER}"
            ),
            expected_entities=("AUTH_HEADER", "EMAIL"),
            sensitive_markers=(_SYNTHETIC_EMAIL, _SYNTHETIC_BEARER),
            benign_markers=("INFO", _BENIGN_CASE_ID),
        ),
        ReplayCase(
            case_id="trace-before-export",
            boundary="trace",
            channel=Channel.TRACE_SPAN_ATTRIBUTES.value,
            mode="data",
            payload={
                "span.name": f"{_BENIGN_CASE_ID}.lookup",
                "db.statement": (
                    "SELECT id FROM users WHERE email = "
                    f"'{_SYNTHETIC_EMAIL}'"
                ),
                "db.system": "postgres",
            },
            expected_entities=("EMAIL",),
            sensitive_markers=(_SYNTHETIC_EMAIL,),
            benign_markers=(_BENIGN_CASE_ID, "postgres"),
        ),
    )


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _same_shape(original: Any, redacted: Any) -> bool:
    if isinstance(original, dict):
        if not isinstance(redacted, dict) or set(original) != set(redacted):
            return False
        return all(_same_shape(original[key], redacted[key]) for key in original)
    if isinstance(original, list):
        if not isinstance(redacted, list) or len(original) != len(redacted):
            return False
        return all(_same_shape(left, right) for left, right in zip(original, redacted))
    if isinstance(original, tuple):
        if not isinstance(redacted, tuple) or len(original) != len(redacted):
            return False
        return all(_same_shape(left, right) for left, right in zip(original, redacted))
    if isinstance(original, str):
        return isinstance(redacted, str)
    return bool(original == redacted)


def _finding_counts(findings: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.type] = counts.get(finding.type, 0) + 1
    return counts


def run_replay_case(case: ReplayCase, veil: Veil) -> ReplayOutcome:
    """Run one case and return evidence that cannot reveal its raw payload."""

    raw_input = _serialize(case.payload)
    input_sha256 = _sha256(raw_input)
    failures: list[str] = []

    try:
        if case.mode == "text":
            result = veil.redact_text(case.payload, channel=case.channel)
        elif case.mode == "data":
            result = veil.redact_data(case.payload, channel=case.channel)
        else:
            raise ValueError("replay mode must be 'text' or 'data'")
    except BlockedSensitiveData as exc:
        counts = _finding_counts(exc.findings)
        if not case.expect_blocked:
            failures.append("unexpected fail-closed block")
        if sorted(counts) != sorted(case.expected_entities):
            failures.append("detected entity types differ from expected")
        if any(finding.raw is not None for finding in exc.findings):
            failures.append("blocked finding stored a raw value")
        return ReplayOutcome(
            case_id=case.case_id,
            boundary=case.boundary,
            channel=case.channel,
            blocked=True,
            input_sha256=input_sha256,
            output_sha256="",
            finding_count=sum(counts.values()),
            redacted_count=0,
            leak_count=0,
            benign_preserved=True,
            structure_preserved=True,
            counts_by_type=counts,
            failures=tuple(failures),
        )

    if case.expect_blocked:
        failures.append("expected fail-closed block but redaction returned")

    safe_output = _serialize(result.data)
    counts = dict(result.stats.counts_by_type)
    leak_count = sum(marker in safe_output for marker in case.sensitive_markers)
    benign_preserved = all(marker in safe_output for marker in case.benign_markers)
    structure_preserved = case.mode == "text" or _same_shape(case.payload, result.data)

    if sorted(counts) != sorted(case.expected_entities):
        failures.append("detected entity types differ from expected")
    if leak_count:
        failures.append("one or more sensitive markers survived redaction")
    if not benign_preserved:
        failures.append("one or more benign markers were not preserved")
    if not structure_preserved:
        failures.append("structured payload shape changed")
    if any(finding.raw is not None for finding in result.findings):
        failures.append("finding stored a raw value")

    finding_count = sum(counts.values())
    return ReplayOutcome(
        case_id=case.case_id,
        boundary=case.boundary,
        channel=case.channel,
        blocked=False,
        input_sha256=input_sha256,
        output_sha256=_sha256(safe_output),
        finding_count=finding_count,
        redacted_count=finding_count,
        leak_count=leak_count,
        benign_preserved=benign_preserved,
        structure_preserved=structure_preserved,
        counts_by_type=counts,
        failures=tuple(failures),
    )


def run_privacy_replay(
    cases: Sequence[ReplayCase] | None = None,
    veil: Veil | None = None,
) -> tuple[ReplayOutcome, ...]:
    """Run the deterministic six-boundary replay without network access."""

    selected_cases = tuple(cases) if cases is not None else default_replay_cases()
    replay_veil = veil or Veil.high(secret=_REPLAY_SECRET, scope=_REPLAY_SCOPE)
    return tuple(run_replay_case(case, replay_veil) for case in selected_cases)


def run_resume_case(case: ReplayCase, veil: Veil) -> ResumeOutcome | None:
    """Redact a case, then re-cross the same boundary with the redacted state.

    Returns ``None`` for fail-closed cases, which never persist an output to
    resume from. The returned evidence cannot reveal the raw payload.
    """

    if case.expect_blocked:
        return None
    try:
        if case.mode == "text":
            first = veil.redact_text(case.payload, channel=case.channel)
            resumed = veil.redact_text(first.data, channel=case.channel)
        elif case.mode == "data":
            first = veil.redact_data(case.payload, channel=case.channel)
            resumed = veil.redact_data(first.data, channel=case.channel)
        else:
            raise ValueError("replay mode must be 'text' or 'data'")
    except BlockedSensitiveData:
        return None

    first_output = _serialize(first.data)
    resumed_output = _serialize(resumed.data)
    leak_count = sum(marker in resumed_output for marker in case.sensitive_markers)
    resume_finding_count = sum(dict(resumed.stats.counts_by_type).values())
    byte_stable = resumed_output == first_output

    failures: list[str] = []
    if leak_count:
        failures.append("a sensitive marker returned after resume")
    if any(finding.raw is not None for finding in resumed.findings):
        failures.append("resumed finding stored a raw value")

    return ResumeOutcome(
        case_id=case.case_id,
        boundary=case.boundary,
        channel=case.channel,
        leak_count=leak_count,
        resume_finding_count=resume_finding_count,
        byte_stable=byte_stable,
        first_output_sha256=_sha256(first_output),
        resumed_output_sha256=_sha256(resumed_output),
        failures=tuple(failures),
    )


def run_resume_safety(
    cases: Sequence[ReplayCase] | None = None,
    veil: Veil | None = None,
) -> tuple[ResumeOutcome, ...]:
    """Run the resume-safety pass over every non-blocked boundary case."""

    selected_cases = tuple(cases) if cases is not None else default_replay_cases()
    replay_veil = veil or Veil.high(secret=_REPLAY_SECRET, scope=_REPLAY_SCOPE)
    outcomes = (run_resume_case(case, replay_veil) for case in selected_cases)
    return tuple(outcome for outcome in outcomes if outcome is not None)


def build_replay_report(
    outcomes: Sequence[ReplayOutcome],
    resume_outcomes: Sequence[ResumeOutcome] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, privacy-safe report.

    When ``resume_outcomes`` is provided, the report gains a ``resume_safety``
    section proving that persisted, redacted state stays safe when a resumed
    checkpoint re-crosses the same boundary, and the top-level gate reflects it.
    """

    passed = sum(outcome.passed for outcome in outcomes)
    findings = sum(outcome.finding_count for outcome in outcomes)
    redacted = sum(outcome.redacted_count for outcome in outcomes)
    leaks = sum(outcome.leak_count for outcome in outcomes)
    boundaries = {outcome.boundary for outcome in outcomes}
    report: dict[str, Any] = {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "project": "pyveil",
        "replay": "privacy-boundary-replay",
        "gate": "pass" if passed == len(outcomes) else "fail",
        "totals": {
            "boundaries": len(boundaries),
            "cases": len(outcomes),
            "passed": passed,
            "failed": len(outcomes) - passed,
            "findings": findings,
            "redacted": redacted,
            "leaks": leaks,
        },
        "cases": [outcome.as_dict() for outcome in outcomes],
        "privacy_note": (
            "Built-in synthetic inputs are never emitted. The report contains "
            "only case ids, channels, counts, booleans, and SHA-256 hashes."
        ),
    }
    if resume_outcomes is not None:
        resume_passed = sum(outcome.passed for outcome in resume_outcomes)
        leaked_markers = sum(outcome.leak_count for outcome in resume_outcomes)
        byte_stable_cases = sum(outcome.byte_stable for outcome in resume_outcomes)
        resume_gate_pass = resume_passed == len(resume_outcomes)
        report["resume_safety"] = {
            "gate": "pass" if resume_gate_pass else "fail",
            "totals": {
                "resumed_cases": len(resume_outcomes),
                "passed": resume_passed,
                "failed": len(resume_outcomes) - resume_passed,
                "leaked_markers": leaked_markers,
                "byte_stable_cases": byte_stable_cases,
            },
            "cases": [outcome.as_dict() for outcome in resume_outcomes],
            "note": (
                "Each case re-crosses its boundary with already-redacted state, "
                "modelling a resumed checkpoint. No synthetic marker returns; "
                "byte_stable records whether re-redaction is a fixed point, since "
                "a value-only placeholder can be re-masked without restoring the "
                "original."
            ),
        }
        if not resume_gate_pass:
            report["gate"] = "fail"
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report as a compact task-oriented evidence table."""

    totals = report["totals"]
    lines = [
        "# pyveil Privacy Boundary Replay",
        "",
        "Deterministic offline evidence for prompt, tool-call, MCP, memory, log, "
        "and trace boundaries. No raw fixture input or redacted payload is shown.",
        "",
        f"- Gate: **{report['gate']}**",
        f"- Boundaries: **{totals['boundaries']}**",
        f"- Cases: **{totals['passed']}/{totals['cases']} passing**",
        f"- Findings: **{totals['findings']}**",
        f"- Leaks: **{totals['leaks']}**",
        "",
        "| Boundary | Channel | Findings | Leaks | Benign preserved | Shape preserved | Gate |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {case['boundary']} | `{case['channel']}` | {case['finding_count']} "
            f"| {case['leak_count']} | {str(case['benign_preserved']).lower()} "
            f"| {str(case['structure_preserved']).lower()} | {case['gate']} |"
        )
    resume = report.get("resume_safety")
    if resume:
        resume_totals = resume["totals"]
        lines.extend(
            [
                "",
                "## Resume Safety",
                "",
                "Each boundary is re-crossed with already-redacted state, modelling "
                "a resumed checkpoint. No synthetic marker returns; `byte_stable` "
                "records whether re-redaction is a fixed point.",
                "",
                f"- Gate: **{resume['gate']}**",
                f"- Resumed cases: "
                f"**{resume_totals['passed']}/{resume_totals['resumed_cases']} passing**",
                f"- Leaked markers: **{resume_totals['leaked_markers']}**",
                f"- Byte-stable cases: "
                f"**{resume_totals['byte_stable_cases']}/{resume_totals['resumed_cases']}**",
                "",
                "| Boundary | Channel | Leaked | Byte stable | Gate |",
                "| --- | --- | ---: | --- | --- |",
            ]
        )
        for case in resume["cases"]:
            lines.append(
                f"| {case['boundary']} | `{case['channel']}` | {case['leak_count']} "
                f"| {str(case['byte_stable']).lower()} | {case['gate']} |"
            )
    lines.append("")
    return "\n".join(lines)


def replay_output(output_format: str = "json") -> tuple[str, int]:
    """Return rendered replay output and its gate-based process exit code."""

    report = build_replay_report(run_privacy_replay(), run_resume_safety())
    if output_format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    elif output_format == "markdown":
        rendered = render_markdown(report)
    else:
        raise ValueError("output format must be 'json' or 'markdown'")
    return rendered, 0 if report["gate"] == "pass" else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the replay CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    rendered, exit_code = replay_output(args.format)
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
