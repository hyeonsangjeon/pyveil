import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pyveil import __version__
from pyveil.cli import main
from pyveil.file_run import EXAMPLE_INPUT, FileRunError, init_run_config, run_file
from pyveil.run_config import RunConfigError, load_run_config


def make_config(tmp_path, **changes):
    path = tmp_path / "pyveil.json"
    init_run_config(path, example=True)
    update_config(path, **changes)
    return path


def update_config(path, **changes):
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update(changes)
    path.write_text(json.dumps(config), encoding="utf-8")


def test_init_produces_executable_config_and_private_unique_key(tmp_path):
    path = make_config(tmp_path)

    config = load_run_config(path)

    assert config.input_format == "json"
    assert config.input_origin == "synthetic"
    assert config.secret_env is None
    assert config.secret_file is not None
    assert config.secret_file.read_text().strip()
    assert config.input_path.is_file()
    if os.name == "posix":
        assert config.secret_file.stat().st_mode & 0o777 == 0o600
    another = tmp_path / "another"
    another.mkdir()
    second = make_config(another)
    second_config = load_run_config(second)
    assert second_config.secret_file is not None
    assert config.secret_file.read_bytes() != second_config.secret_file.read_bytes()


def test_checked_in_ledger_and_example_match_the_release():
    root = Path(__file__).resolve().parents[1]
    config = load_run_config(root / "pyveil.json")
    assert config.secret_env == "PYVEIL_SECRET"
    assert json.loads(config.input_path.read_text()) == EXAMPLE_INPUT
    assert config.input_origin == "synthetic"


def test_real_file_run_is_reproducible_and_does_not_overwrite_input(tmp_path):
    path = make_config(tmp_path)
    config = load_run_config(path)
    assert config.secret_file is not None
    input_before = config.input_path.read_bytes()

    first = run_file(path)
    second = run_file(path)

    assert first.output != second.output
    assert first.output.read_bytes() == second.output.read_bytes()
    assert config.input_path.read_bytes() == input_before
    payload = json.loads(first.output.read_text())
    assert payload["ticket"] == 42
    assert payload["urgent"] is False
    assert "[EMAIL:" in payload["message"]
    assert payload["headers"]["Authorization"].startswith("[AUTH_HEADER:")
    receipt = json.loads(first.receipt.read_text())
    assert receipt == first.report
    assert receipt["pyveil_version"] == __version__
    assert receipt["config_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert receipt["output_sha256"] == hashlib.sha256(first.output.read_bytes()).hexdigest()
    assert receipt["findings"]["by_type"] == {"AUTH_HEADER": 1, "EMAIL": 1}
    assert receipt["findings"]["redacted"] == 2
    assert receipt["findings"]["passed"] == 0
    assert receipt["execution"] == {
        "kind": "local-file-redaction",
        "measured": True,
        "input_origin": "synthetic",
        "provider_called": False,
        "network": "none",
    }
    assert receipt["input_hmac_sha256"] != hashlib.sha256(input_before).hexdigest()
    assert receipt["input_hmac_sha256"] == second.report["input_hmac_sha256"]
    assert receipt["key_id"] == second.report["key_id"]
    for private in (
        "tutorial.user@example.com",
        "TUTORIAL_ONLY_NOT_A_CREDENTIAL",
        config.secret_file.read_text().strip(),
        str(tmp_path),
    ):
        assert private not in first.receipt.read_text()
    assert sorted(p.name for p in first.output.parent.iterdir()) == [
        "receipt.json",
        "redacted.json",
    ]
    if os.name == "posix":
        assert first.output.stat().st_mode & 0o777 == 0o600
        assert first.output.parent.stat().st_mode & 0o777 == 0o700


def test_run_uses_config_directory_not_cwd_or_environment_defaults(tmp_path, monkeypatch):
    path = make_config(tmp_path)
    expected = run_file(path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("PYVEIL_SCOPE", "not-the-ledger")
    monkeypatch.setenv("PYVEIL_SECRET", "not-the-ledger-key")

    actual = run_file(path)

    assert actual.output.read_bytes() == expected.output.read_bytes()


def test_text_file_preserves_crlf_and_only_redacts_findings(tmp_path):
    path = tmp_path / "pyveil.json"
    text = tmp_path / "notes.txt"
    text.write_bytes(b"Owner tutorial.user@example.com\r\nTicket 42\r\n")
    init_run_config(path, input_path="notes.txt")

    result = run_file(path)

    assert result.output.suffix == ".txt"
    assert result.output.read_bytes().startswith(b"Owner [EMAIL:")
    assert result.output.read_bytes().endswith(b"\r\nTicket 42\r\n")
    assert result.report["execution"]["input_origin"] == "user-provided"


def test_json_arrays_preserve_nested_values(tmp_path):
    path = make_config(tmp_path)
    config = load_run_config(path)
    config.input_path.write_text(
        json.dumps([{"email": "tutorial.user@example.com"}, True, 42, None])
    )

    result = run_file(path)

    payload = json.loads(result.output.read_text())
    assert payload[0]["email"].startswith("[EMAIL:")
    assert payload[1:] == [True, 42, None]


def test_blocked_run_has_no_output_and_no_raw_stderr(tmp_path, capsys):
    path = make_config(tmp_path, channel="tool.call.arguments")

    assert main(["run", str(path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "AUTH_HEADER" in captured.err
    assert "TUTORIAL_ONLY_NOT_A_CREDENTIAL" not in captured.err
    assert not (tmp_path / ".pyveil-runs").exists()


def test_action_override_is_executed_and_reported_as_pass(tmp_path):
    path = make_config(tmp_path, actions={"EMAIL": "PASS"})

    result = run_file(path)

    assert json.loads(result.output.read_text())["message"] == EXAMPLE_INPUT["message"]
    assert result.report["findings"]["passed"] == 1
    assert result.report["findings"]["redacted"] == 1


def test_low_level_is_actually_applied(tmp_path):
    path = make_config(tmp_path, level="LOW")

    result = run_file(path)

    assert "[AUTH_HEADER]" in result.output.read_text()
    assert "tu" in json.loads(result.output.read_text())["message"]
    assert result.report["level"] == "LOW"


def test_env_secret_is_explicit_and_required(tmp_path, monkeypatch):
    path = tmp_path / "pyveil.json"
    init_run_config(path, example=True, secret_env="FILE_REDACTION_KEY")
    monkeypatch.delenv("FILE_REDACTION_KEY", raising=False)
    monkeypatch.setenv("PYVEIL_SECRET", "must-not-be-used")
    assert not (tmp_path / ".pyveil.key").exists()
    with pytest.raises(RunConfigError, match="missing or empty"):
        run_file(path)
    monkeypatch.setenv("FILE_REDACTION_KEY", "chosen-runtime-key")

    first = run_file(path)
    monkeypatch.setenv("FILE_REDACTION_KEY", "a-different-key")
    second = run_file(path)

    assert first.output.read_bytes() != second.output.read_bytes()
    assert first.report["key_id"] != second.report["key_id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": True},
        {"schema_version": 2},
        {"pyveil_version": "0.0.0"},
        {"channel": "prompt.intput"},
        {"level": "maybe"},
        {"input_format": "auto"},
        {"input_origin": "measured"},
        {"max_input_chars": True},
        {"max_input_chars": 0},
        {"max_input_chars": 1_000_001},
        {"actions": []},
        {"actions": {"EMAIL": "allow"}},
        {"actions": {"EMIAL": "PASS"}},
        {"input": ""},
        {"scope": ""},
        {"secret_env": "ALSO_SET"},
        {"secret": "do-not-echo-this"},
        {"extra": "do-not-ignore-this"},
        {"scope": "\ud800"},
        {"input": "\x00"},
    ],
)
def test_invalid_config_is_rejected_before_output(tmp_path, changes, capsys):
    path = make_config(tmp_path, **changes)

    assert main(["run", str(path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "do-not-echo-this" not in captured.err
    assert not (tmp_path / ".pyveil-runs").exists()


@pytest.mark.parametrize(
    "content",
    ['{"schema_version":1,"schema_version":1}', "{}", "[]", "null", '{"x":NaN}', "# comments only"],
)
def test_config_requires_strict_complete_json(tmp_path, content):
    path = tmp_path / "pyveil.json"
    path.write_text(content)

    with pytest.raises(RunConfigError):
        load_run_config(path)


def test_input_limits_are_checked_before_redaction_and_output(tmp_path):
    path = make_config(tmp_path, max_input_chars=5)

    with pytest.raises(RunConfigError, match="max_input_chars"):
        run_file(path)
    assert not (tmp_path / ".pyveil-runs").exists()


@pytest.mark.parametrize(
    "text",
    [
        '{"email":"first@example.com","email":"second@example.com"}',
        '{"x":NaN}',
        '{"x":1e999}',
        '{"x":',
        '"not an object"',
        '{"value":"\\ud800"}',
    ],
)
def test_invalid_json_input_does_not_fall_back_to_text(tmp_path, text, capsys):
    path = make_config(tmp_path)
    load_run_config(path).input_path.write_text(text)

    assert main(["run", str(path)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "first@example.com" not in captured.err
    assert not (tmp_path / ".pyveil-runs").exists()


def test_missing_key_never_generates_replacement(tmp_path):
    path = make_config(tmp_path)
    config = load_run_config(path)
    assert config.secret_file is not None
    config.secret_file.unlink()

    with pytest.raises(RunConfigError, match="restore"):
        run_file(path)
    assert not config.secret_file.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permissions")
def test_public_key_file_is_rejected(tmp_path):
    path = make_config(tmp_path)
    config = load_run_config(path)
    assert config.secret_file is not None
    config.secret_file.chmod(0o644)

    with pytest.raises(RunConfigError, match="chmod 600"):
        run_file(path)


@pytest.mark.parametrize("name", ["pyveil.json", ".pyveil.key", "input.example.json"])
def test_init_never_overwrites_existing_files(tmp_path, name):
    existing = tmp_path / name
    existing.write_text("keep me")

    with pytest.raises(RunConfigError, match="overwrite"):
        init_run_config(tmp_path / "pyveil.json", example=True)

    assert existing.read_text() == "keep me"
    assert sorted(p.name for p in tmp_path.iterdir()) == [name]


@pytest.mark.parametrize("input_name", ["pyveil.json", ".pyveil.key"])
def test_init_rejects_input_config_key_aliases(tmp_path, input_name):
    with pytest.raises(RunConfigError, match="input must not"):
        init_run_config(tmp_path / "pyveil.json", input_path=input_name)
    assert not list(tmp_path.iterdir())


def test_load_rejects_input_alias_to_key(tmp_path):
    path = make_config(tmp_path, input=".pyveil.key")
    with pytest.raises(RunConfigError, match="input must not"):
        load_run_config(path)


def test_load_rejects_hardlinked_secret_input(tmp_path):
    path = make_config(tmp_path)
    config = load_run_config(path)
    assert config.secret_file is not None
    alias = tmp_path / "key-copy.txt"
    os.link(config.secret_file, alias)
    update_config(path, input=alias.name, input_format="text")

    with pytest.raises(RunConfigError, match="input must not"):
        run_file(path)
    assert not config.output_dir.exists()


def test_load_rejects_config_as_secret(tmp_path):
    path = make_config(tmp_path, secret_file="pyveil.json")
    with pytest.raises(RunConfigError, match="secret_file must not"):
        run_file(path)


def test_missing_input_and_output_fail_with_no_false_success(tmp_path, capsys):
    path = make_config(tmp_path)
    config = load_run_config(path)
    config.input_path.unlink()
    assert main(["run", str(path)]) == 1
    assert capsys.readouterr().out == ""
    config.input_path.write_text(json.dumps(EXAMPLE_INPUT))
    config.output_dir.write_text("not a directory")
    assert main(["run", str(path)]) == 1
    assert capsys.readouterr().out == ""


def test_atomic_run_does_not_publish_half_a_result(tmp_path, monkeypatch):
    path = make_config(tmp_path)
    from pyveil import file_run

    original = file_run._write_private

    def fail_receipt(target, content):
        if target.name == "receipt.json":
            raise OSError("simulated disk-full error")
        original(target, content)

    monkeypatch.setattr(file_run, "_write_private", fail_receipt)
    with pytest.raises(FileRunError, match="persist"):
        run_file(path)
    assert list((tmp_path / ".pyveil-runs").iterdir()) == []


def test_cli_run_json_returns_locations_not_content(tmp_path, capsys):
    path = make_config(tmp_path)

    assert main(["run", str(path), "--format", "json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "completed"
    assert Path(output["output"]).is_file()
    assert Path(output["receipt"]).is_file()
    assert "tutorial.user@example.com" not in str(output)


def test_module_subprocess_runs_from_another_directory(tmp_path):
    path = make_config(tmp_path)
    package_root = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ, PYTHONPATH=package_root)
    completed = subprocess.run(
        [sys.executable, "-m", "pyveil", "run", str(path), "--format", "json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr
    assert Path(json.loads(completed.stdout)["output"]).is_file()
