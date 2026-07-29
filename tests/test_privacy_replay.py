"""Privacy Boundary Replay contracts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pyveil import Veil
from pyveil.privacy_replay import (
    ReplayCase,
    build_replay_report,
    default_replay_cases,
    replay_output,
    run_privacy_replay,
    run_replay_case,
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
