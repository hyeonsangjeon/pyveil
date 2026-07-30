"""Privacy Boundary Replay contracts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pyveil import Veil
from pyveil.privacy_replay import (
    ReplayCase,
    ResumeOutcome,
    build_replay_report,
    default_replay_cases,
    replay_output,
    run_privacy_replay,
    run_replay_case,
    run_resume_case,
    run_resume_safety,
)

EXPECTED_BOUNDARIES = {"prompt", "tool_call", "mcp", "memory", "log", "trace"}


def test_default_replay_covers_six_boundaries_without_leaks():
    cases = default_replay_cases()
    outcomes = run_privacy_replay(cases)
    report = build_replay_report(outcomes)

    assert {outcome.boundary for outcome in outcomes} == EXPECTED_BOUNDARIES
    assert report["gate"] == "pass"
    assert report["totals"] == {
        "boundaries": 6,
        "cases": 6,
        "passed": 6,
        "failed": 0,
        "findings": 10,
        "redacted": 10,
        "leaks": 0,
    }
    assert all(outcome.benign_preserved for outcome in outcomes)
    assert all(outcome.structure_preserved for outcome in outcomes)


def test_replay_report_contains_no_raw_fixture_markers():
    cases = default_replay_cases()
    report = build_replay_report(run_privacy_replay(cases))
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    for case in cases:
        assert case.payload not in report["cases"]
        for marker in case.sensitive_markers:
            assert marker not in serialized


def test_replay_is_deterministic_for_the_same_cases_and_scope():
    first = build_replay_report(run_privacy_replay())
    second = build_replay_report(run_privacy_replay())

    assert first == second
    assert all(case["input_sha256"] for case in first["cases"])
    assert all(case["output_sha256"] for case in first["cases"])


def test_replay_gate_fails_when_a_sensitive_marker_survives():
    planted = ReplayCase(
        case_id="planted-leak",
        boundary="prompt",
        channel="prompt.input",
        mode="text",
        payload="Keep SYNTHETIC-UNSUPPORTED-MARKER in this test.",
        expected_entities=(),
        sensitive_markers=("SYNTHETIC-UNSUPPORTED-MARKER",),
        benign_markers=("Keep",),
    )
    veil = Veil.high(secret=b"replay-test-secret", scope="replay/test")

    outcome = run_replay_case(planted, veil)

    assert outcome.passed is False
    assert outcome.leak_count == 1
    assert outcome.failures == ("one or more sensitive markers survived redaction",)


def test_replay_case_records_expected_fail_closed_without_output():
    synthetic_key = "sk-proj-EXAMPLEabcdefghijklmnopqrstuvwx"
    blocked_case = ReplayCase(
        case_id="tool-credential-block",
        boundary="tool_call",
        channel="tool.call.arguments",
        mode="data",
        payload={"tool": "http_get", "api_key": synthetic_key},
        expected_entities=("API_KEY",),
        sensitive_markers=(synthetic_key,),
        benign_markers=(),
        expect_blocked=True,
    )
    veil = Veil.high(secret=b"replay-test-secret", scope="replay/test")

    outcome = run_replay_case(blocked_case, veil)

    assert outcome.passed is True
    assert outcome.blocked is True
    assert outcome.finding_count == 1
    assert outcome.redacted_count == 0
    assert outcome.leak_count == 0
    assert outcome.output_sha256 == ""


def test_replay_json_and_markdown_outputs_are_privacy_safe():
    json_output, json_exit = replay_output("json")
    markdown_output, markdown_exit = replay_output("markdown")
    report = json.loads(json_output)

    assert json_exit == 0
    assert markdown_exit == 0
    assert report["gate"] == "pass"
    assert report["totals"]["leaks"] == 0
    assert "# pyveil Privacy Boundary Replay" in markdown_output
    assert "alice@example.com" not in json_output + markdown_output
    assert "replay.user@example.com" not in json_output + markdown_output


def test_replay_output_rejects_unknown_format():
    with pytest.raises(ValueError, match="output format"):
        replay_output("xml")


def test_privacy_replay_example_runs_keyless():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "examples" / "privacy_replay.py"), "--format", "json"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    report = json.loads(completed.stdout)
    assert report["gate"] == "pass"
    assert report["totals"]["boundaries"] == 6
    assert report["totals"]["leaks"] == 0


def test_resume_safety_never_restores_a_marker_across_default_boundaries():
    outcomes = run_resume_safety()

    assert len(outcomes) == 6
    assert all(outcome.passed for outcome in outcomes)
    assert all(outcome.leak_count == 0 for outcome in outcomes)
    assert all(isinstance(outcome, ResumeOutcome) for outcome in outcomes)
    assert all(outcome.first_output_sha256 for outcome in outcomes)
    assert all(outcome.resumed_output_sha256 for outcome in outcomes)
    # At least one boundary re-redacts to a byte-identical fixed point.
    assert any(outcome.byte_stable for outcome in outcomes)


def test_resume_of_value_only_placeholder_is_safe_but_not_byte_stable():
    # A value-only URL query secret is re-masked on resume: its placeholder is
    # replaced with a fresh one, but the original token never returns.
    case = ReplayCase(
        case_id="resume-url-secret",
        boundary="mcp",
        channel="mcp.resource.content",
        mode="data",
        payload={
            "text": (
                "open https://api.example.com/cb?"
                "access_token=EXAMPLEsecrettoken98765"
            )
        },
        expected_entities=("URL_QUERY_SECRET",),
        sensitive_markers=("EXAMPLEsecrettoken98765",),
        benign_markers=(),
    )
    veil = Veil.high(secret=b"replay-test-secret", scope="replay/test")

    outcome = run_resume_case(case, veil)

    assert outcome is not None
    assert outcome.passed is True
    assert outcome.leak_count == 0
    assert outcome.byte_stable is False


def test_resume_gate_fails_when_a_marker_survives_the_resumed_boundary():
    planted = ReplayCase(
        case_id="planted-resume-leak",
        boundary="prompt",
        channel="prompt.input",
        mode="text",
        payload="Keep SYNTHETIC-UNSUPPORTED-MARKER across a resume.",
        expected_entities=(),
        sensitive_markers=("SYNTHETIC-UNSUPPORTED-MARKER",),
        benign_markers=("Keep",),
    )
    veil = Veil.high(secret=b"replay-test-secret", scope="replay/test")

    outcome = run_resume_case(planted, veil)

    assert outcome is not None
    assert outcome.passed is False
    assert outcome.leak_count == 1
    assert outcome.failures == ("a sensitive marker returned after resume",)


def test_resume_skips_fail_closed_cases():
    synthetic_key = "sk-proj-EXAMPLEabcdefghijklmnopqrstuvwx"
    blocked_case = ReplayCase(
        case_id="tool-credential-block",
        boundary="tool_call",
        channel="tool.call.arguments",
        mode="data",
        payload={"tool": "http_get", "api_key": synthetic_key},
        expected_entities=("API_KEY",),
        sensitive_markers=(synthetic_key,),
        benign_markers=(),
        expect_blocked=True,
    )
    veil = Veil.high(secret=b"replay-test-secret", scope="replay/test")

    assert run_resume_case(blocked_case, veil) is None
    assert run_resume_safety((blocked_case,)) == ()


def test_report_includes_resume_safety_and_folds_into_the_gate():
    cases = default_replay_cases()
    report = build_replay_report(run_privacy_replay(cases), run_resume_safety(cases))

    resume = report["resume_safety"]
    assert resume["gate"] == "pass"
    assert resume["totals"]["resumed_cases"] == 6
    assert resume["totals"]["leaked_markers"] == 0
    assert report["gate"] == "pass"
    # The six-boundary totals block is untouched by the resume section.
    assert set(report["totals"]) == {
        "boundaries",
        "cases",
        "passed",
        "failed",
        "findings",
        "redacted",
        "leaks",
    }

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for case in cases:
        for marker in case.sensitive_markers:
            assert marker not in serialized


def test_report_without_resume_outcomes_has_no_resume_section():
    report = build_replay_report(run_privacy_replay())

    assert "resume_safety" not in report


def test_markdown_output_includes_a_resume_safety_section():
    markdown_output, exit_code = replay_output("markdown")

    assert exit_code == 0
    assert "# pyveil Privacy Boundary Replay" in markdown_output
    assert "## Resume Safety" in markdown_output
