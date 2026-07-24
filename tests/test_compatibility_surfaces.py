"""Synthetic protection-surface compatibility tests (Channel coverage).

These tests exercise redaction across every public ``Channel`` with synthetic,
clearly fake PII and secrets. They assert that sensitive values are removed,
JSON structure and non-sensitive fields are preserved, credentials fail closed
in tool arguments, and no raw sensitive value is ever stored on a finding or
surfaced through the shared harness.
"""

import json

import pytest

from pyveil import BlockedSensitiveData, Veil
from pyveil.constants import Channel
from scripts.compat_harness import (
    CHANNEL_VALUES,
    KNOWN_CATEGORIES,
    KNOWN_MODES,
    build_veil,
    load_fixtures,
    load_manifest,
    run_fixture,
)

FIXTURE_PAYLOAD = load_fixtures()
FIXTURES = FIXTURE_PAYLOAD["fixtures"]
MANIFEST = load_manifest()
ALL_ENTITY_TYPES = {
    "EMAIL",
    "PHONE",
    "CREDIT_CARD",
    "JWT",
    "AUTH_HEADER",
    "PRIVATE_KEY",
    "API_KEY",
    "URL_QUERY_SECRET",
    "KV_SECRET",
}


def _fixture_ids():
    return [fixture["id"] for fixture in FIXTURES]


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_fixture_meets_expectations(fixture):
    veil = build_veil(FIXTURE_PAYLOAD)
    outcome = run_fixture(veil, fixture)
    assert outcome.passed, f"{fixture['id']}: {outcome.failures}"


@pytest.mark.parametrize("fixture", FIXTURES, ids=_fixture_ids())
def test_fixture_schema_is_well_formed(fixture):
    assert fixture["channel"] in CHANNEL_VALUES
    assert fixture["category"] in KNOWN_CATEGORIES
    assert fixture["mode"] in KNOWN_MODES
    assert isinstance(fixture["expect_entities"], list)
    assert isinstance(fixture["expect_absent"], list)
    assert isinstance(fixture["expect_preserved"], list)


def test_every_channel_has_a_fixture():
    covered = {fixture["channel"] for fixture in FIXTURES}
    assert covered == {channel.value for channel in Channel}


def test_every_entity_type_is_exercised():
    seen = set()
    for fixture in FIXTURES:
        seen.update(fixture["expect_entities"])
    assert ALL_ENTITY_TYPES <= seen


def test_all_edge_categories_are_present():
    categories = {fixture["category"] for fixture in FIXTURES}
    for required in ("nested", "unicode", "broken_json", "false_positive", "fail_closed"):
        assert required in categories, f"missing edge category: {required}"


def test_tool_arguments_fail_closed_on_credentials():
    veil = Veil.high(secret=b"surface-test-secret", scope="surface/test")
    payload = {"headers": {"api_key": "sk-proj-EXAMPLEabcdefghijklmnopqrstuvwx"}}
    with pytest.raises(BlockedSensitiveData) as excinfo:
        veil.redact_data(payload, channel=Channel.TOOL_CALL_ARGUMENTS)
    assert excinfo.value.channel == "tool.call.arguments"
    assert {finding.type for finding in excinfo.value.findings} == {"API_KEY"}
    assert all(finding.raw is None for finding in excinfo.value.findings)


def test_broken_json_falls_back_to_text_without_raising():
    veil = Veil.high(secret=b"surface-test-secret", scope="surface/test")
    result = veil.redact_data(
        '{"email":"alice@example.com","ok":true', channel=Channel.LOG_RECORD
    )
    assert isinstance(result.data, str)
    assert "alice@example.com" not in result.data


def test_false_positive_span_attributes_are_untouched():
    veil = Veil.high(secret=b"surface-test-secret", scope="surface/test")
    payload = {"order.id": "1234 5678 9012 3456", "user.tier": "gold"}
    result = veil.redact_data(payload, channel=Channel.TRACE_SPAN_ATTRIBUTES)
    assert result.data == payload
    assert result.findings == ()


def test_nested_structure_and_non_sensitive_fields_are_preserved():
    veil = Veil.high(secret=b"surface-test-secret", scope="surface/test")
    payload = {
        "rows": [{"email": "alice@example.com", "name": "Synthetic User"}],
        "count": 1,
        "ok": True,
    }
    result = veil.redact_data(payload, channel=Channel.TOOL_CALL_RESULT)
    assert result.data["count"] == 1
    assert result.data["ok"] is True
    assert result.data["rows"][0]["name"] == "Synthetic User"
    assert "alice@example.com" not in json.dumps(result.data)


def test_harness_detects_a_leak_regression():
    """Meta-test: the harness must fail when a sensitive value survives."""

    veil = build_veil(FIXTURE_PAYLOAD)
    leaky = {
        "id": "leaky_probe",
        "channel": "prompt.input",
        "category": "basic",
        "mode": "text",
        "input": "Ship order gold-42 to alice@example.com",
        "expect_entities": ["EMAIL"],
        # gold-42 is non-sensitive and survives, so this absence claim must fail.
        "expect_absent": ["gold-42"],
        "expect_preserved": [],
    }
    outcome = run_fixture(veil, leaky)
    assert not outcome.passed
    assert any("expected-absent" in reason for reason in outcome.failures)


def test_manifest_surfaces_reference_existing_fixtures():
    known_ids = set(_fixture_ids())
    referenced = []
    for surface in MANIFEST["surfaces"]:
        assert surface["channel"] in CHANNEL_VALUES
        assert surface["status"] in MANIFEST["status_vocabulary"]
        for fixture_id in surface["fixture_ids"]:
            assert fixture_id in known_ids, f"unknown fixture: {fixture_id}"
            referenced.append(fixture_id)
    # Every fixture is referenced by exactly one surface, and none is orphaned.
    assert sorted(referenced) == sorted(known_ids)


def test_manifest_channels_match_fixture_channels():
    for surface in MANIFEST["surfaces"]:
        for fixture in FIXTURES:
            if fixture["id"] in surface["fixture_ids"]:
                assert fixture["channel"] == surface["channel"]
