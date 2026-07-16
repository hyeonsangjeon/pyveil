from types import SimpleNamespace
from typing import Any

import pytest

from pyveil.integrations import anthropic as anthropic_integration
from pyveil.integrations.anthropic import (
    AnthropicCallError,
    AnthropicCallResult,
    AnthropicConfigError,
    AnthropicSettings,
    ask_anthropic,
    load_settings,
    main,
)

ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MAX_TOKENS",
    "ANTHROPIC_TIMEOUT",
    "PYVEIL_SECRET",
    "PYVEIL_SCOPE",
    "CUSTOM_ANTHROPIC_KEY",
    "CUSTOM_PYVEIL_SECRET",
)


def clear_example_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_uses_safe_dry_run_defaults(monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")

    settings = load_settings(require_anthropic=False)

    assert settings.model is None
    assert settings.api_key is None
    assert settings.base_url is None
    assert settings.max_tokens == 256
    assert settings.timeout_seconds == 120.0
    assert settings.pyveil_scope == "anthropic/example"
    assert "test-secret" not in repr(settings)


def test_load_settings_combines_yaml_and_secret_environment(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "anthropic.yaml"
    config.write_text(
        """anthropic:
  model: yaml-model
  base_url: https://gateway.example.test
  max_tokens: 512
  timeout_seconds: 45
  api_key_env: CUSTOM_ANTHROPIC_KEY
pyveil:
  secret_env: CUSTOM_PYVEIL_SECRET
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_ANTHROPIC_KEY", "synthetic-anthropic-key")
    monkeypatch.setenv("CUSTOM_PYVEIL_SECRET", "synthetic-pyveil-secret")

    settings = load_settings(config_path=config)

    assert settings.model == "yaml-model"
    assert settings.base_url == "https://gateway.example.test"
    assert settings.max_tokens == 512
    assert settings.timeout_seconds == 45.0
    assert settings.api_key == "synthetic-anthropic-key"
    assert settings.pyveil_secret == "synthetic-pyveil-secret"
    assert settings.pyveil_scope == "yaml-scope"
    assert "synthetic-anthropic-key" not in repr(settings)
    assert "synthetic-pyveil-secret" not in repr(settings)


def test_process_environment_then_dotenv_override_yaml(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "anthropic.yaml"
    config.write_text(
        """anthropic:
  model: yaml-model
  max_tokens: 128
pyveil:
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        """ANTHROPIC_API_KEY=dotenv-key
ANTHROPIC_MODEL=dotenv-model
ANTHROPIC_MAX_TOKENS=384
PYVEIL_SECRET=dotenv-secret
PYVEIL_SCOPE=dotenv-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_MODEL", "process-model")
    monkeypatch.setenv("PYVEIL_SCOPE", "process-scope")

    settings = load_settings(config_path=config, env_file=env_file)

    assert settings.model == "process-model"
    assert settings.max_tokens == 384
    assert settings.api_key == "dotenv-key"
    assert settings.pyveil_secret == "dotenv-secret"
    assert settings.pyveil_scope == "process-scope"


@pytest.mark.parametrize(
    "yaml_text",
    [
        "anthropic:\n  api_key: do-not-store-this-here\n",
        "pyveil:\n  secret: do-not-store-this-here\n",
    ],
)
def test_yaml_rejects_plaintext_secrets(yaml_text, tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    config = tmp_path / "unsafe.yaml"
    config.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(AnthropicConfigError, match="do not store"):
        load_settings(config_path=config, require_anthropic=False)


def test_load_settings_requires_live_provider_values(monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")

    with pytest.raises(AnthropicConfigError, match="ANTHROPIC_MODEL, ANTHROPIC_API_KEY"):
        load_settings()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pyveil_secret": ""}, "secret must not be empty"),
        ({"model": "  "}, "model must not be empty"),
        ({"base_url": "file:///tmp/anthropic"}, "http or https URL"),
        ({"base_url": "https://user:pass@example.test"}, "must not contain credentials"),
        ({"base_url": "https://example.test?key=value"}, "query or fragment"),
        ({"max_tokens": 0}, "max_tokens must be between"),
        ({"timeout_seconds": 0}, "timeout_seconds must be between"),
    ],
)
def test_settings_validate_rejects_invalid_direct_values(changes, message):
    values: dict[str, Any] = {
        "pyveil_secret": "test-secret",
        "api_key": "synthetic-key",
        "model": "test-model",
    }
    values.update(changes)

    with pytest.raises(AnthropicConfigError, match=message):
        AnthropicSettings(**values).validate()


def test_ask_anthropic_sends_only_redacted_text_and_reports_usage():
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking="not returned"),
                    SimpleNamespace(type="text", text="Protected contacts are ready."),
                ],
                usage=SimpleNamespace(input_tokens=28, output_tokens=7),
                _request_id="req_synthetic",
            )

    settings = AnthropicSettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
        pyveil_scope="test/session",
        max_tokens=96,
    )
    result = ask_anthropic(
        "Contact alice@example.com or 010-1234-5678.",
        settings,
        client=SimpleNamespace(messages=FakeMessages()),
    )

    assert captured["model"] == "test-model"
    assert captured["max_tokens"] == 96
    sent = captured["messages"][0]["content"]
    assert captured["messages"][0]["role"] == "user"
    assert "alice@example.com" not in sent
    assert "010-1234-5678" not in sent
    assert "[EMAIL:" in sent
    assert "[PHONE:" in sent
    assert result.finding_counts == {"EMAIL": 1, "PHONE": 1}
    assert result.output_text == "Protected contacts are ready."
    assert result.input_tokens == 28
    assert result.output_tokens == 7
    assert result.request_id == "req_synthetic"


def test_ask_anthropic_joins_text_blocks_and_ignores_other_content():
    response = {
        "content": [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "name": "synthetic"},
            {"type": "text", "text": " second"},
        ]
    }
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    settings = AnthropicSettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
    )

    result = ask_anthropic("Summarize alice@example.com.", settings, client=client)

    assert result.output_text == "first second"
    assert result.input_tokens is None
    assert result.output_tokens is None


def test_ask_anthropic_rejects_response_without_text_content():
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kwargs: {"content": []})
    )
    settings = AnthropicSettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
    )

    with pytest.raises(AnthropicCallError, match="did not include text content"):
        ask_anthropic("Summarize alice@example.com.", settings, client=client)


def test_ask_anthropic_wraps_client_error_without_raw_prompt():
    class FailingMessages:
        def create(self, **kwargs):
            raise RuntimeError("synthetic connection failure")

    settings = AnthropicSettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
    )
    raw_prompt = "Contact alice@example.com."

    with pytest.raises(AnthropicCallError) as exc_info:
        ask_anthropic(raw_prompt, settings, client=SimpleNamespace(messages=FailingMessages()))

    assert raw_prompt not in str(exc_info.value)
    assert "alice@example.com" not in str(exc_info.value)


def test_dry_run_needs_no_provider_key_and_prints_safe_boundary(capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "dry-run-secret")

    exit_code = main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "010-1234-5678" not in captured.out
    assert "model: not configured" in captured.out
    assert "sent-to-anthropic: Write a one-sentence support follow-up for [EMAIL:" in captured.out
    assert "findings: EMAIL=1, PHONE=1" in captured.out
    assert "anthropic-response: skipped (--dry-run)" in captured.out


def test_live_cli_reads_prompt_file_and_prints_metrics(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Contact alice@example.com.", encoding="utf-8")

    def fake_ask(prompt, settings):
        assert prompt == "Contact alice@example.com."
        assert settings.model == "test-model"
        return AnthropicCallResult(
            redacted_input="Contact [EMAIL:synthetic].",
            finding_counts={"EMAIL": 1},
            output_text="safe response",
            input_tokens=12,
            output_tokens=4,
        )

    monkeypatch.setattr(anthropic_integration, "ask_anthropic", fake_ask)

    assert main(["--prompt-file", str(prompt_file)]) == 0
    captured = capsys.readouterr()
    assert "alice@example.com" not in captured.out
    assert "anthropic-response: safe response" in captured.out
    assert "input_tokens=12, output_tokens=4" in captured.out


def test_cli_returns_safe_errors(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)

    assert main(["--dry-run"]) == 2
    assert "pyveil HMAC secret is required" in capsys.readouterr().err

    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    assert main(["--dry-run", "--prompt-file", str(tmp_path / "missing.txt")]) == 2
    assert "prompt file does not exist" in capsys.readouterr().err

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")

    def fail_safely(prompt, settings):
        raise AnthropicCallError("synthetic safe failure")

    monkeypatch.setattr(anthropic_integration, "ask_anthropic", fail_safely)
    assert main(["--prompt", "alice@example.com"]) == 3
    captured = capsys.readouterr()
    assert "anthropic error: synthetic safe failure" in captured.err
    assert "alice@example.com" not in captured.err
