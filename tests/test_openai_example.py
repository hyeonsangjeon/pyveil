from types import SimpleNamespace
from typing import Any

import pytest

from pyveil.integrations import openai as openai_integration
from pyveil.integrations.openai import (
    OpenAICallError,
    OpenAICallResult,
    OpenAIConfigError,
    OpenAISettings,
    ask_openai,
    load_settings,
    main,
)

ENV_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "OPENAI_TIMEOUT",
    "PYVEIL_SECRET",
    "PYVEIL_SCOPE",
    "CUSTOM_OPENAI_KEY",
    "CUSTOM_PYVEIL_SECRET",
)


def clear_example_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_uses_safe_dry_run_defaults(monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")

    settings = load_settings(require_openai=False)

    assert settings.model is None
    assert settings.api_key is None
    assert settings.base_url is None
    assert settings.max_output_tokens == 256
    assert settings.timeout_seconds == 120.0
    assert settings.pyveil_scope == "openai/example"
    assert "test-secret" not in repr(settings)


def test_load_settings_combines_yaml_and_secret_environment(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "openai.yaml"
    config.write_text(
        """openai:
  model: yaml-model
  base_url: https://gateway.example.test/v1
  max_output_tokens: 512
  timeout_seconds: 45
  api_key_env: CUSTOM_OPENAI_KEY
pyveil:
  secret_env: CUSTOM_PYVEIL_SECRET
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_OPENAI_KEY", "synthetic-openai-key")
    monkeypatch.setenv("CUSTOM_PYVEIL_SECRET", "synthetic-pyveil-secret")

    settings = load_settings(config_path=config)

    assert settings.model == "yaml-model"
    assert settings.base_url == "https://gateway.example.test/v1"
    assert settings.max_output_tokens == 512
    assert settings.timeout_seconds == 45.0
    assert settings.api_key == "synthetic-openai-key"
    assert settings.pyveil_secret == "synthetic-pyveil-secret"
    assert settings.pyveil_scope == "yaml-scope"
    assert "synthetic-openai-key" not in repr(settings)
    assert "synthetic-pyveil-secret" not in repr(settings)


def test_process_environment_then_dotenv_override_yaml(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "openai.yaml"
    config.write_text(
        """openai:
  model: yaml-model
  max_output_tokens: 128
pyveil:
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        """OPENAI_API_KEY=dotenv-key
OPENAI_MODEL=dotenv-model
OPENAI_MAX_OUTPUT_TOKENS=384
PYVEIL_SECRET=dotenv-secret
PYVEIL_SCOPE=dotenv-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_MODEL", "process-model")
    monkeypatch.setenv("PYVEIL_SCOPE", "process-scope")

    settings = load_settings(config_path=config, env_file=env_file)

    assert settings.model == "process-model"
    assert settings.max_output_tokens == 384
    assert settings.api_key == "dotenv-key"
    assert settings.pyveil_secret == "dotenv-secret"
    assert settings.pyveil_scope == "process-scope"


@pytest.mark.parametrize(
    "yaml_text",
    [
        "openai:\n  api_key: do-not-store-this-here\n",
        "pyveil:\n  secret: do-not-store-this-here\n",
    ],
)
def test_yaml_rejects_plaintext_secrets(yaml_text, tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    config = tmp_path / "unsafe.yaml"
    config.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(OpenAIConfigError, match="do not store"):
        load_settings(config_path=config, require_openai=False)


def test_load_settings_requires_live_provider_values(monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")

    with pytest.raises(OpenAIConfigError, match="OPENAI_MODEL, OPENAI_API_KEY"):
        load_settings()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pyveil_secret": ""}, "secret must not be empty"),
        ({"model": "  "}, "model must not be empty"),
        ({"base_url": "file:///tmp/openai"}, "http or https URL"),
        ({"base_url": "https://user:pass@example.test/v1"}, "must not contain credentials"),
        ({"base_url": "https://example.test/v1?key=value"}, "query or fragment"),
        ({"max_output_tokens": 0}, "max_output_tokens must be between"),
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

    with pytest.raises(OpenAIConfigError, match=message):
        OpenAISettings(**values).validate()


def test_ask_openai_sends_only_redacted_text_and_reports_usage():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text="I can follow up using the protected contacts.",
                usage=SimpleNamespace(input_tokens=32, output_tokens=9, total_tokens=41),
                _request_id="req_synthetic",
            )

    settings = OpenAISettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
        pyveil_scope="test/session",
        max_output_tokens=96,
    )
    result = ask_openai(
        "Contact alice@example.com or 010-1234-5678.",
        settings,
        client=SimpleNamespace(responses=FakeResponses()),
    )

    assert captured["model"] == "test-model"
    assert captured["max_output_tokens"] == 96
    assert "alice@example.com" not in captured["input"]
    assert "010-1234-5678" not in captured["input"]
    assert "[EMAIL:" in captured["input"]
    assert "[PHONE:" in captured["input"]
    assert result.finding_counts == {"EMAIL": 1, "PHONE": 1}
    assert result.output_text == "I can follow up using the protected contacts."
    assert result.input_tokens == 32
    assert result.output_tokens == 9
    assert result.total_tokens == 41
    assert result.request_id == "req_synthetic"


def test_ask_openai_rejects_response_without_output_text():
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kwargs: {"output_text": ""})
    )
    settings = OpenAISettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
    )

    with pytest.raises(OpenAICallError, match="did not include output_text"):
        ask_openai("Summarize alice@example.com.", settings, client=client)


def test_ask_openai_wraps_client_error_without_raw_prompt():
    class FailingResponses:
        def create(self, **kwargs):
            raise RuntimeError("synthetic connection failure")

    settings = OpenAISettings(
        pyveil_secret="test-secret",
        api_key="synthetic-key",
        model="test-model",
    )
    raw_prompt = "Contact alice@example.com."

    with pytest.raises(OpenAICallError) as exc_info:
        ask_openai(raw_prompt, settings, client=SimpleNamespace(responses=FailingResponses()))

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
    assert "sent-to-openai: Write a one-sentence support follow-up for [EMAIL:" in captured.out
    assert "findings: EMAIL=1, PHONE=1" in captured.out
    assert "openai-response: skipped (--dry-run)" in captured.out


def test_live_cli_reads_prompt_file_and_prints_metrics(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Contact alice@example.com.", encoding="utf-8")

    def fake_ask(prompt, settings):
        assert prompt == "Contact alice@example.com."
        assert settings.model == "test-model"
        return OpenAICallResult(
            redacted_input="Contact [EMAIL:synthetic].",
            finding_counts={"EMAIL": 1},
            output_text="safe response",
            input_tokens=12,
            output_tokens=4,
            total_tokens=16,
        )

    monkeypatch.setattr(openai_integration, "ask_openai", fake_ask)

    assert main(["--prompt-file", str(prompt_file)]) == 0
    captured = capsys.readouterr()
    assert "alice@example.com" not in captured.out
    assert "openai-response: safe response" in captured.out
    assert "input_tokens=12, output_tokens=4, total_tokens=16" in captured.out


def test_cli_returns_safe_errors(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)

    assert main(["--dry-run"]) == 2
    assert "pyveil HMAC secret is required" in capsys.readouterr().err

    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    assert main(["--dry-run", "--prompt-file", str(tmp_path / "missing.txt")]) == 2
    assert "prompt file does not exist" in capsys.readouterr().err

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    def fail_safely(prompt, settings):
        raise OpenAICallError("synthetic safe failure")

    monkeypatch.setattr(openai_integration, "ask_openai", fail_safely)
    assert main(["--prompt", "alice@example.com"]) == 3
    captured = capsys.readouterr()
    assert "openai error: synthetic safe failure" in captured.err
    assert "alice@example.com" not in captured.err
