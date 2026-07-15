from dataclasses import replace
from types import SimpleNamespace

import pytest

import pyveil.integrations.ollama as ollama_integration
from pyveil.integrations.ollama import (
    OllamaCallError,
    OllamaCallResult,
    OllamaConfigError,
    OllamaSettings,
    ask_ollama,
    load_settings,
    main,
)

ENV_NAMES = (
    "OLLAMA_HOST",
    "OLLAMA_MODEL",
    "OLLAMA_NUM_CTX",
    "OLLAMA_NUM_PREDICT",
    "OLLAMA_TEMPERATURE",
    "OLLAMA_KEEP_ALIVE",
    "OLLAMA_TIMEOUT",
    "PYVEIL_SECRET",
    "PYVEIL_SCOPE",
    "CUSTOM_PYVEIL_SECRET",
)


def clear_example_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_uses_memory_safe_defaults(monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "synthetic-pyveil-secret")

    settings = load_settings()

    assert settings.host == "http://127.0.0.1:11434"
    assert settings.model == "qwen3.5:4b"
    assert settings.num_ctx == 4096
    assert settings.num_predict == 128
    assert settings.temperature == 0.2
    assert settings.keep_alive == "0"
    assert settings.timeout_seconds == 120.0
    assert "synthetic-pyveil-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"model": ""}, "model must not be empty"),
        ({"pyveil_secret": ""}, "secret must not be empty"),
        ({"num_predict": True}, "num_predict must be between"),
        ({"temperature": True}, "temperature must be between"),
        ({"keep_alive": ""}, "keep_alive must not be empty"),
    ],
)
def test_settings_validate_rejects_invalid_direct_values(changes, message):
    settings = replace(OllamaSettings(pyveil_secret="test-secret"), **changes)

    with pytest.raises(OllamaConfigError, match=message):
        settings.validate()


def test_load_settings_combines_yaml_and_secret_environment(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "ollama.yaml"
    config.write_text(
        """ollama:
  host: 127.0.0.1:11434
  model: yaml-model:4b
  num_ctx: 2048
  num_predict: 64
  temperature: 0.1
  keep_alive: 0
  timeout_seconds: 45
pyveil:
  secret_env: CUSTOM_PYVEIL_SECRET
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_PYVEIL_SECRET", "synthetic-pyveil-secret")

    settings = load_settings(config_path=config)

    assert settings.host == "http://127.0.0.1:11434"
    assert settings.model == "yaml-model:4b"
    assert settings.num_ctx == 2048
    assert settings.num_predict == 64
    assert settings.temperature == 0.1
    assert settings.keep_alive == "0"
    assert settings.timeout_seconds == 45.0
    assert settings.pyveil_scope == "yaml-scope"


def test_process_environment_then_dotenv_override_yaml(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    config = tmp_path / "ollama.yaml"
    config.write_text(
        """ollama:
  host: http://yaml-host:11434
  model: yaml-model:4b
  num_ctx: 2048
pyveil:
  scope: yaml-scope
""",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        """OLLAMA_HOST=http://dotenv-host:11434
OLLAMA_MODEL=dotenv-model:4b
OLLAMA_NUM_CTX=3072
PYVEIL_SECRET=dotenv-secret
PYVEIL_SCOPE=dotenv-scope
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OLLAMA_HOST", "http://process-host:11434")
    monkeypatch.setenv("PYVEIL_SCOPE", "process-scope")

    settings = load_settings(config_path=config, env_file=env_file)

    assert settings.host == "http://process-host:11434"
    assert settings.model == "dotenv-model:4b"
    assert settings.num_ctx == 3072
    assert settings.pyveil_secret == "dotenv-secret"
    assert settings.pyveil_scope == "process-scope"


def test_yaml_rejects_plaintext_pyveil_secret(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    config = tmp_path / "unsafe.yaml"
    config.write_text(
        """pyveil:
  secret: do-not-store-this-here
""",
        encoding="utf-8",
    )

    with pytest.raises(OllamaConfigError, match="do not store secret in YAML"):
        load_settings(config_path=config)


@pytest.mark.parametrize(
    ("yaml_text", "message"),
    [
        ("- not\n- a\n- mapping\n", "top-level mapping"),
        ("ollama: []\n", "ollama must be a YAML mapping"),
        ("ollama:\n  model: 42\n", "model must be a string"),
        ("ollama:\n  keep_alive: []\n", "duration string or number"),
    ],
)
def test_load_settings_rejects_invalid_yaml_shapes(yaml_text, message, tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    config = tmp_path / "invalid.yaml"
    config.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(OllamaConfigError, match=message):
        load_settings(config_path=config)


def test_load_settings_reports_missing_files(tmp_path, monkeypatch):
    clear_example_environment(monkeypatch)

    with pytest.raises(OllamaConfigError, match="env file does not exist"):
        load_settings(env_file=tmp_path / "missing.env")
    with pytest.raises(OllamaConfigError, match="YAML config does not exist"):
        load_settings(config_path=tmp_path / "missing.yaml")


def test_load_settings_requires_pyveil_secret(monkeypatch):
    clear_example_environment(monkeypatch)

    with pytest.raises(OllamaConfigError, match="pyveil HMAC secret is required"):
        load_settings()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("OLLAMA_HOST", "file:///tmp/ollama.sock", "http or https URL"),
        ("OLLAMA_HOST", "http://user:pass@localhost:11434", "must not contain credentials"),
        ("OLLAMA_NUM_CTX", "128", "between 512 and 262144"),
        ("OLLAMA_NUM_PREDICT", "0", "between 1 and 4096"),
        ("OLLAMA_TEMPERATURE", "3", "between 0.0 and 2.0"),
        ("OLLAMA_TIMEOUT", "0", "between 1.0 and 3600.0"),
    ],
)
def test_load_settings_rejects_invalid_runtime_values(name, value, message, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    monkeypatch.setenv(name, value)

    with pytest.raises(OllamaConfigError, match=message):
        load_settings()


def test_ask_ollama_sends_only_redacted_text_to_client():
    captured = {}

    class FakeClient:
        def chat(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                message=SimpleNamespace(content="보호된 연락처로 후속 안내를 보내겠습니다."),
                total_duration=2_500_000_000,
                load_duration=500_000_000,
                prompt_eval_count=31,
                eval_count=18,
            )

    settings = OllamaSettings(
        pyveil_secret="test-secret",
        model="qwen3.5:4b",
        pyveil_scope="test/session",
        num_ctx=4096,
        num_predict=96,
        temperature=0.1,
        keep_alive="0",
    )

    result = ask_ollama(
        "Contact alice@example.com or 010-1234-5678.",
        settings,
        client=FakeClient(),
    )

    sent = captured["messages"][0]["content"]
    assert captured["model"] == "qwen3.5:4b"
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["options"] == {
        "num_ctx": 4096,
        "num_predict": 96,
        "temperature": 0.1,
    }
    assert captured["keep_alive"] == "0"
    assert "alice@example.com" not in sent
    assert "010-1234-5678" not in sent
    assert "[EMAIL:" in sent
    assert "[PHONE:" in sent
    assert result.finding_counts == {"EMAIL": 1, "PHONE": 1}
    assert result.output_text == "보호된 연락처로 후속 안내를 보내겠습니다."
    assert result.total_duration_ms == 2500.0
    assert result.load_duration_ms == 500.0
    assert result.prompt_eval_count == 31
    assert result.eval_count == 18


def test_ask_ollama_accepts_mapping_response_without_metrics():
    class MappingClient:
        def chat(self, **kwargs):
            return {"message": {"content": "safe response"}, "total_duration": True}

    result = ask_ollama(
        "Summarize alice@example.com.",
        OllamaSettings(pyveil_secret="test-secret"),
        client=MappingClient(),
    )

    assert result.output_text == "safe response"
    assert result.total_duration_ms is None
    assert result.load_duration_ms is None
    assert result.prompt_eval_count is None
    assert result.eval_count is None


def test_ask_ollama_rejects_response_without_content():
    class EmptyClient:
        def chat(self, **kwargs):
            return {"message": {"content": ""}}

    with pytest.raises(OllamaCallError, match="did not include message.content"):
        ask_ollama(
            "Summarize alice@example.com.",
            OllamaSettings(pyveil_secret="test-secret"),
            client=EmptyClient(),
        )


def test_ask_ollama_wraps_client_error_without_raw_prompt():
    class FailingClient:
        def chat(self, **kwargs):
            raise RuntimeError("synthetic connection failure")

    settings = OllamaSettings(pyveil_secret="test-secret")
    raw_prompt = "Contact alice@example.com."

    with pytest.raises(OllamaCallError) as exc_info:
        ask_ollama(raw_prompt, settings, client=FailingClient())

    assert raw_prompt not in str(exc_info.value)
    assert "alice@example.com" not in str(exc_info.value)


def test_dry_run_needs_only_pyveil_secret_and_prints_safe_boundary(capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "dry-run-secret")

    exit_code = main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "010-1234-5678" not in captured.out
    assert "model: qwen3.5:4b" in captured.out
    assert "host: http://127.0.0.1:11434" in captured.out
    assert "sent-to-ollama: Write a one-sentence support follow-up for [EMAIL:" in captured.out
    assert "findings: EMAIL=1, PHONE=1" in captured.out
    assert "ollama-response: skipped (--dry-run)" in captured.out


def test_dry_run_reports_no_findings_for_safe_prompt(capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "dry-run-secret")

    exit_code = main(["--dry-run", "--prompt", "Hello from a safe local prompt."])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "findings: none" in captured.out


def test_live_cli_reads_prompt_file_and_prints_metrics(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Contact alice@example.com.", encoding="utf-8")

    def fake_ask(prompt, settings):
        assert prompt == "Contact alice@example.com."
        return OllamaCallResult(
            redacted_input="Contact [EMAIL:synthetic].",
            finding_counts={"EMAIL": 1},
            output_text="safe response",
            total_duration_ms=1250.0,
            load_duration_ms=250.0,
            prompt_eval_count=12,
            eval_count=4,
        )

    monkeypatch.setattr(ollama_integration, "ask_ollama", fake_ask)

    exit_code = main(["--prompt-file", str(prompt_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "ollama-response: safe response" in captured.out
    assert "total_ms=1250.0" in captured.out
    assert "load_ms=250.0" in captured.out
    assert "prompt_tokens=12" in captured.out
    assert "output_tokens=4" in captured.out


def test_cli_returns_safe_errors(tmp_path, capsys, monkeypatch):
    clear_example_environment(monkeypatch)

    assert main(["--dry-run"]) == 2
    assert "configuration error: pyveil HMAC secret is required" in capsys.readouterr().err

    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    assert main(["--prompt-file", str(tmp_path / "missing.txt")]) == 2
    assert "prompt file does not exist" in capsys.readouterr().err

    def fail_safely(prompt, settings):
        raise OllamaCallError("synthetic safe failure")

    monkeypatch.setattr(ollama_integration, "ask_ollama", fail_safely)
    assert main(["--prompt", "alice@example.com"]) == 3
    captured = capsys.readouterr()
    assert "ollama error: synthetic safe failure" in captured.err
    assert "alice@example.com" not in captured.err
