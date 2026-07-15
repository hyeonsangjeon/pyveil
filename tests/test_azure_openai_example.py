from types import SimpleNamespace

import pytest

from pyveil.integrations.azure_openai import (
    AzureOpenAISettings,
    ConfigError,
    ask_azure_openai,
    load_settings,
    main,
)

ENV_NAMES = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_KEY",
    "PYVEIL_SECRET",
    "PYVEIL_SCOPE",
    "CUSTOM_AZURE_KEY",
    "CUSTOM_PYVEIL_SECRET",
)


def clear_example_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_combines_yaml_and_secret_environment(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "azure.yaml"
    config.write_text(
        """azure_openai:
  endpoint: https://yaml-resource.openai.azure.com
  deployment: yaml-deployment
  api_key_env: CUSTOM_AZURE_KEY
pyveil:
  secret_env: CUSTOM_PYVEIL_SECRET
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_AZURE_KEY", "synthetic-azure-key")
    monkeypatch.setenv("CUSTOM_PYVEIL_SECRET", "synthetic-pyveil-secret")

    settings = load_settings(config_path=config)

    assert settings.endpoint == "https://yaml-resource.openai.azure.com"
    assert settings.deployment == "yaml-deployment"
    assert settings.api_key == "synthetic-azure-key"
    assert settings.pyveil_secret == "synthetic-pyveil-secret"
    assert settings.pyveil_scope == "yaml-scope"
    assert "synthetic-azure-key" not in repr(settings)
    assert "synthetic-pyveil-secret" not in repr(settings)


def test_process_environment_then_dotenv_override_yaml(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "azure.yaml"
    config.write_text(
        """azure_openai:
  endpoint: https://yaml-resource.openai.azure.com
  deployment: yaml-deployment
pyveil:
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        """AZURE_OPENAI_ENDPOINT=https://dotenv-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=dotenv-deployment
AZURE_OPENAI_API_KEY=dotenv-key
PYVEIL_SECRET=dotenv-secret
PYVEIL_SCOPE=dotenv-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://process-resource.openai.azure.com")
    monkeypatch.setenv("PYVEIL_SCOPE", "process-scope")

    settings = load_settings(config_path=config, env_file=env_file)

    assert settings.endpoint == "https://process-resource.openai.azure.com"
    assert settings.deployment == "dotenv-deployment"
    assert settings.api_key == "dotenv-key"
    assert settings.pyveil_secret == "dotenv-secret"
    assert settings.pyveil_scope == "process-scope"


def test_yaml_rejects_plaintext_secrets(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    config = tmp_path / "unsafe.yaml"
    config.write_text(
        """azure_openai:
  api_key: do-not-store-this-here
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="do not store api_key in YAML"):
        load_settings(config_path=config, require_azure=False)


def test_ask_azure_sends_only_redacted_text_to_client():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="I can follow up using the protected contacts.")

    fake_client = SimpleNamespace(responses=FakeResponses())
    settings = AzureOpenAISettings(
        endpoint="https://resource.openai.azure.com",
        deployment="test-deployment",
        api_key="synthetic-key",
        pyveil_secret="test-secret",
        pyveil_scope="test/session",
    )
    assert settings.base_url == "https://resource.openai.azure.com/openai/v1/"

    result = ask_azure_openai(
        "Contact alice@example.com or 010-1234-5678.",
        settings,
        client=fake_client,
    )

    assert captured["model"] == "test-deployment"
    assert "alice@example.com" not in captured["input"]
    assert "010-1234-5678" not in captured["input"]
    assert "[EMAIL:" in captured["input"]
    assert "[PHONE:" in captured["input"]
    assert result.finding_counts == {"EMAIL": 1, "PHONE": 1}
    assert result.output_text == "I can follow up using the protected contacts."


def test_dry_run_needs_only_pyveil_secret_and_prints_safe_boundary(capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "dry-run-secret")

    exit_code = main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "010-1234-5678" not in captured.out
    assert "sent-to-azure: Write a one-sentence support follow-up for [EMAIL:" in captured.out
    assert "findings: EMAIL=1, PHONE=1" in captured.out
    assert "azure-response: skipped (--dry-run)" in captured.out
