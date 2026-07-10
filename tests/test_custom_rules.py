import re
from typing import Any, cast

import pytest

from pyveil import Action, BlockedSensitiveData, Channel, CustomRule, Policy, Veil, redact_text


def test_custom_regex_rule_redacts_domain_identifier():
    rule = CustomRule("CUSTOMER_ID", r"\bCUS-[A-Z0-9]{8}\b", rule_id="customer_id")
    veil = Veil.high(secret=b"test-secret", rules=[rule])

    result = veil.redact_text("customer CUS-A1B2C3D4")

    assert "CUS-A1B2C3D4" not in result.text
    assert "[CUSTOMER_ID:" in result.text
    assert result.findings[0].detector == "custom_rule"
    assert result.findings[0].rule_id == "customer_id"
    assert result.findings[0].raw is None


def test_exact_rule_redacts_known_names_without_partial_matches():
    rule = CustomRule.exact("PERSON", ["Alice Kim", "Ann"])
    veil = Veil.high(secret=b"test-secret", rules=[rule])

    result = veil.redact_text("Alice Kim met Ann and Annette")

    assert "Alice Kim" not in result.text
    assert " met Ann " not in result.text
    assert "Annette" in result.text
    assert [finding.detector for finding in result.findings] == ["known_value", "known_value"]


def test_exact_rule_can_match_case_insensitively():
    rule = CustomRule.exact("PROJECT_NAME", "Project Atlas", ignore_case=True)
    veil = Veil.high(secret=b"test-secret", rules=[rule])

    result = veil.redact_text("PROJECT ATLAS")

    assert result.text.startswith("[PROJECT_NAME:")


def test_custom_rule_repr_does_not_expose_known_values():
    rule = CustomRule.exact("PERSON", "Alice Kim")

    assert "Alice Kim" not in repr(rule)
    assert "PERSON" in repr(rule)


def test_builtin_credential_detector_wins_over_overlapping_custom_rule():
    key = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    rule = CustomRule.exact("INTERNAL_LABEL", key)
    veil = Veil.high(secret=b"test-secret", rules=[rule])

    result = veil.redact_text(key)

    assert result.findings[0].type == "API_KEY"


def test_custom_rule_supports_compiled_patterns_and_low_masking():
    rule = CustomRule("TICKET", re.compile(r"TKT-\d{4}"))
    veil = Veil.low(secret=b"test-secret", rules=[rule])

    result = veil.redact_text("TKT-2048")

    assert result.text == "[TICKET]"


def test_module_helper_accepts_custom_rules():
    result = redact_text(
        "order ORD-123456",
        secret=b"test-secret",
        rules=[CustomRule("ORDER_ID", r"\bORD-\d{6}\b")],
    )

    assert "[ORDER_ID:" in result.text


def test_custom_rule_redacts_structured_data_and_reports_path():
    veil = Veil.high(
        secret=b"test-secret",
        rules=[CustomRule.exact("PERSON", "Alice Kim")],
    )

    result = veil.redact_data({"owner": "Alice Kim"}, channel=Channel.PROMPT_INPUT)

    assert result.data["owner"].startswith("[PERSON:")
    assert result.findings[0].path == "/owner"


def test_policy_can_block_custom_entity_without_raw_value():
    policy = Policy.default_high().override(
        Channel.TOOL_CALL_ARGUMENTS,
        "CUSTOMER_ID",
        Action.BLOCK,
    )
    veil = Veil.high(
        secret=b"test-secret",
        policy=policy,
        rules=[CustomRule("CUSTOMER_ID", r"\bCUS-[A-Z0-9]{8}\b")],
    )

    with pytest.raises(BlockedSensitiveData) as exc_info:
        veil.redact_text("CUS-A1B2C3D4", channel=Channel.TOOL_CALL_ARGUMENTS)

    assert "CUS-A1B2C3D4" not in str(exc_info.value)
    assert exc_info.value.findings[0].raw is None


@pytest.mark.parametrize(
    "rule",
    [
        lambda: CustomRule("not-valid", r"x"),
        lambda: CustomRule("VALID", r"x", confidence=1.5),
        lambda: CustomRule.exact("PERSON", []),
    ],
)
def test_invalid_custom_rules_are_rejected(rule):
    with pytest.raises(ValueError):
        rule()


def test_veil_rejects_non_custom_rule_values():
    with pytest.raises(TypeError, match="CustomRule"):
        Veil.high(secret=b"test-secret", rules=cast(Any, [re.compile("x")]))


def test_custom_rule_rejects_non_text_patterns():
    with pytest.raises(TypeError, match="compiled text regex"):
        CustomRule("CUSTOM", cast(Any, re.compile(b"bytes")))
