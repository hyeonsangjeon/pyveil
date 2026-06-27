import logging
import re
from typing import Any, cast

import pytest

from pyveil import (
    Action,
    BlockedSensitiveData,
    Channel,
    Entity,
    Level,
    Policy,
    Veil,
    redact_data,
    redact_text,
)
from pyveil.integrations import PyVeilLogFilter


def test_high_redacts_prompt_with_stable_placeholders():
    veil = Veil.high(secret=b"test-secret", scope="session-a")

    result = veil.redact_text(
        "Email alice@example.com and call 010-1234-5678.",
        channel="prompt.input",
    )

    assert "alice@example.com" not in result.text
    assert "010-1234-5678" not in result.text
    assert re.search(r"\[EMAIL:[0-9a-f]{12}\]", result.text)
    assert re.search(r"\[PHONE:[0-9a-f]{12}\]", result.text)
    assert result.stats.counts_by_type == {"EMAIL": 1, "PHONE": 1}
    assert all(finding.raw is None for finding in result.findings)


def test_low_preserves_debugging_shape():
    veil = Veil.low(secret=b"test-secret")

    result = veil.redact_text("alice@example.com 010-1234-5678", channel="prompt.input")

    assert "al***@e******.com" in result.text
    assert "010-****-5678" in result.text


def test_low_email_masks_short_segments():
    veil = Veil.low(secret=b"test-secret")

    result = veil.redact_text("a@x.com", channel="prompt.input")

    assert result.text == "*@*.com"


def test_hmac_placeholders_are_scoped_and_deterministic():
    first = Veil.high(secret=b"same", scope="a").redact_text("alice@example.com")
    second = Veil.high(secret=b"same", scope="a").redact_text("alice@example.com")
    third = Veil.high(secret=b"same", scope="b").redact_text("alice@example.com")

    assert first.text == second.text
    assert first.text != third.text


def test_secret_is_required():
    with pytest.raises(TypeError):
        cast(Any, Veil)()
    with pytest.raises(ValueError):
        cast(Any, Veil)(secret=None)


def test_max_input_chars_limits_text_and_structured_payloads():
    veil = Veil.high(secret=b"test-secret", max_input_chars=5)

    with pytest.raises(ValueError, match="max_input_chars"):
        veil.redact_text("alice@example.com")

    with pytest.raises(ValueError, match="max_input_chars"):
        veil.redact_data({"nested": {"email": "alice@example.com"}}, channel="prompt.input")


def test_tool_arguments_block_auth_headers_without_leaking_raw_secret():
    veil = Veil.high(secret=b"test-secret")

    with pytest.raises(BlockedSensitiveData) as exc_info:
        veil.redact_data(
            {"headers": {"Authorization": "Bearer synthetic-secret-token"}},
            channel="tool.call.arguments",
        )

    message = str(exc_info.value)
    assert "AUTH_HEADER=1" in message
    assert "synthetic-secret-token" not in message
    assert all(finding.raw is None for finding in exc_info.value.findings)


def test_tool_arguments_block_keyed_secrets_without_leaking_raw_secret():
    veil = Veil.high(secret=b"test-secret")

    with pytest.raises(BlockedSensitiveData) as exc_info:
        veil.redact_data({"password": "synthetic-password"}, channel="tool.call.arguments")

    message = str(exc_info.value)
    assert "KV_SECRET=1" in message
    assert "synthetic-password" not in message
    assert all(finding.raw is None for finding in exc_info.value.findings)


def test_sensitive_key_non_string_scalars_preserve_type_without_findings():
    veil = Veil.high(secret=b"test-secret")
    payload = {"api_key": 12345, "password": True, "token": None}

    result = veil.redact_data(payload, channel="prompt.input")

    assert result.data == payload
    assert result.findings == ()


def test_sensitive_key_nested_containers_are_still_traversed():
    veil = Veil.high(secret=b"test-secret")

    result = veil.redact_data(
        {"password": {"contact": "alice@example.com"}, "token": ["call 010-1234-5678"]},
        channel="prompt.input",
    )

    assert result.data["password"]["contact"].startswith("[EMAIL:")
    assert "[PHONE:" in result.data["token"][0]
    assert {finding.path for finding in result.findings} == {"/password/contact", "/token/0"}


def test_policy_pass_override_leaves_value_visible_but_records_finding():
    policy = Policy.default_high().override("prompt.input", "EMAIL", Action.PASS)
    veil = Veil.high(secret=b"test-secret", policy=policy)

    result = veil.redact_text("alice@example.com", channel="prompt.input")

    assert result.text == "alice@example.com"
    assert result.findings[0].type == "EMAIL"
    assert result.findings[0].raw is None


def test_policy_pass_override_can_target_structured_api_keys():
    policy = Policy.default_high().override(
        Channel.TOOL_CALL_ARGUMENTS,
        Entity.API_KEY,
        Action.PASS,
    )
    veil = Veil.high(secret=b"test-secret", policy=policy)

    result = veil.redact_data(
        {"api_key": "synthetic-api-key"},
        channel=Channel.TOOL_CALL_ARGUMENTS,
    )

    assert result.data["api_key"] == "synthetic-api-key"
    assert result.findings[0].type == Entity.API_KEY.value
    assert result.findings[0].raw is None


def test_public_channel_and_entity_enums_work_in_policy():
    policy = Policy.default_high().override(Channel.PROMPT_INPUT, Entity.EMAIL, Action.PASS)
    veil = Veil.high(secret=b"test-secret", policy=policy)

    result = veil.redact_text("alice@example.com", channel=Channel.PROMPT_INPUT)

    assert result.text == "alice@example.com"
    assert result.findings[0].type == Entity.EMAIL.value


def test_policy_accepts_enum_keys_in_constructor():
    policy = Policy(
        channel_levels={Channel.PROMPT_INPUT: Level.LOW},
        blocked=frozenset({(Channel.PROMPT_INPUT, Entity.EMAIL)}),
    )

    assert policy.level_for("prompt.input") == Level.LOW
    assert policy.action_for("prompt.input", "EMAIL") == Action.BLOCK


def test_module_level_helpers_use_explicit_or_env_secret(monkeypatch):
    explicit = redact_text("alice@example.com", secret=b"helper-secret")
    assert "[EMAIL:" in explicit.text

    monkeypatch.setenv("PYVEIL_SECRET", "env-secret")
    from_env = redact_data({"email": "alice@example.com"}, channel="prompt.input")

    assert from_env.data["email"].startswith("[EMAIL:")


def test_module_level_helpers_require_secret(monkeypatch):
    monkeypatch.delenv("PYVEIL_SECRET", raising=False)

    with pytest.raises(ValueError, match="secret is required"):
        redact_text("alice@example.com")


def test_logging_filter_redacts_before_export(caplog):
    logger = logging.getLogger("pyveil-test-logger")
    logger.handlers = []
    logger.propagate = True
    logger.addFilter(PyVeilLogFilter(Veil.high(secret=b"log-secret")))

    with caplog.at_level(logging.WARNING):
        logger.warning("email %s", "alice@example.com")

    assert "alice@example.com" not in caplog.text
    assert "[EMAIL:" in caplog.text
