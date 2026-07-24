"""Tests for the compatibility validator and Proof-of-Compatibility Receipt."""

import copy

from scripts.compat_harness import load_fixtures, load_manifest, run_all
from scripts.compatibility_receipt import (
    build_receipt,
    forbidden_tokens,
    render_markdown,
    scan_for_leaks,
)
from scripts.validate_compatibility import render_table, validate


def test_shipped_manifest_and_fixtures_are_valid():
    assert validate(load_manifest(), load_fixtures()) == []


def test_validator_flags_unknown_status_and_missing_fixture():
    manifest = copy.deepcopy(load_manifest())
    manifest["surfaces"][0]["status"] = "definitely-verified"
    manifest["surfaces"][0]["fixture_ids"] = ["no_such_fixture"]
    errors = validate(manifest, load_fixtures())
    assert any("unknown status" in error for error in errors)
    assert any("unknown fixture" in error for error in errors)


def test_validator_flags_orphan_fixture():
    manifest = copy.deepcopy(load_manifest())
    # Drop a fixture reference so one fixture becomes unreferenced.
    manifest["surfaces"][-1]["fixture_ids"] = manifest["surfaces"][-1]["fixture_ids"][:1]
    errors = validate(manifest, load_fixtures())
    assert any("not referenced" in error for error in errors)


def test_rendered_table_lists_every_surface():
    manifest = load_manifest()
    table = render_table(manifest)
    for surface in manifest["surfaces"]:
        assert f"`{surface['channel']}`" in table


def test_receipt_gate_passes_and_summarizes_all_surfaces():
    receipt = build_receipt(run_all())
    assert receipt["gate"] == "pass"
    assert receipt["totals"]["failed"] == 0
    assert receipt["totals"]["surfaces"] == 8
    assert receipt["redaction_summary"]["EMAIL"] >= 1


def test_receipt_contains_no_raw_sensitive_values():
    fixtures = load_fixtures()
    receipt = build_receipt(run_all(fixtures))
    text = render_markdown(receipt)
    import json

    payload = json.dumps(receipt, ensure_ascii=False)
    assert scan_for_leaks(payload + text, forbidden_tokens(fixtures)) == []


def test_leak_scanner_detects_a_planted_token():
    assert scan_for_leaks("prefix alice@example.com suffix", ["alice@example.com"]) == [
        "alice@example.com"
    ]


def test_receipt_never_stores_finding_raw_values():
    receipt = build_receipt(run_all())
    for entries in receipt["surfaces"].values():
        for entry in entries:
            assert "input" not in entry
            assert "raw" not in entry
