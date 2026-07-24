import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pyveil import __version__
from pyveil.cli import main


def test_cli_redact_file(tmp_path, capsys):
    path = tmp_path / "prompt.txt"
    path.write_text("email alice@example.com", encoding="utf-8")

    exit_code = main(["redact", str(path), "--secret", "test-secret"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "[EMAIL:" in captured.out


def test_cli_scan_file(tmp_path, capsys):
    path = tmp_path / "prompt.txt"
    path.write_text("email alice@example.com", encoding="utf-8")

    exit_code = main(["scan", str(path), "--secret", "test-secret", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["stats"]["counts_by_type"] == {"EMAIL": 1}
    assert payload["findings"][0]["type"] == "EMAIL"


def test_cli_init_and_test_config(tmp_path, capsys):
    config_path = tmp_path / "pyveil.yaml"

    init_exit = main(["init", str(config_path)])
    test_exit = main(["test-config", str(config_path)])

    captured = capsys.readouterr()
    assert init_exit == 0
    assert test_exit == 0
    assert "ok" in captured.out


def test_cli_requires_secret_when_env_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("PYVEIL_SECRET", raising=False)
    path = tmp_path / "prompt.txt"
    path.write_text("email alice@example.com", encoding="utf-8")

    exit_code = main(["redact", str(path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "secret is required" in captured.err


def test_cli_uses_env_secret(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PYVEIL_SECRET", "test-secret")
    path = tmp_path / "prompt.txt"
    path.write_text("email alice@example.com", encoding="utf-8")

    exit_code = main(["redact", str(path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "[EMAIL:" in captured.out


def test_cli_redact_json_preserves_structure(tmp_path, capsys):
    path = tmp_path / "payload.json"
    path.write_text(
        json.dumps({"user": {"email": "alice@example.com"}, "debug": True}),
        encoding="utf-8",
    )

    exit_code = main(["redact", str(path), "--secret", "test-secret", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["data"]["debug"] is True
    assert payload["data"]["user"]["email"].startswith("[EMAIL:")
    assert "alice@example.com" not in captured.out


def test_cli_redact_json_requires_json_format_for_structured_output(tmp_path, capsys):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"user": {"email": "alice@example.com"}}), encoding="utf-8")

    exit_code = main(["redact", str(path), "--secret", "test-secret"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "structured JSON input requires --format json" in captured.err


def test_cli_scan_json_reports_json_pointer_paths(tmp_path, capsys):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps({"user": {"email": "alice@example.com"}}), encoding="utf-8")

    exit_code = main(["scan", str(path), "--secret", "test-secret"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["findings"][0]["path"] == "/user/email"


def test_cli_scope_changes_placeholder(tmp_path, capsys):
    path = tmp_path / "prompt.txt"
    path.write_text("email alice@example.com", encoding="utf-8")

    first_exit = main(["redact", str(path), "--secret", "test-secret", "--scope", "tenant/a"])
    first = capsys.readouterr()
    second_exit = main(["redact", str(path), "--secret", "test-secret", "--scope", "tenant/b"])
    second = capsys.readouterr()

    assert first_exit == 0
    assert second_exit == 0
    assert first.out != second.out
    assert "alice@example.com" not in first.out
    assert "alice@example.com" not in second.out


def test_cli_dash_reads_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("email alice@example.com"))

    exit_code = main(["redact", "-", "--secret", "test-secret"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "alice@example.com" not in captured.out
    assert "[EMAIL:" in captured.out


def test_cli_demo_runs_without_secret(capsys, monkeypatch):
    monkeypatch.delenv("PYVEIL_SECRET", raising=False)

    exit_code = main(["demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "before: Email alice@example.com" in captured.out
    assert "after:  Email [EMAIL:" in captured.out
    assert "API_KEY" in captured.out


def test_cli_demo_json_is_machine_readable(capsys):
    exit_code = main(["demo", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["before"].startswith("Email alice@example.com")
    assert "alice@example.com" not in payload["after"]
    assert payload["counts_by_type"] == {"API_KEY": 1, "EMAIL": 1, "PHONE": 1}


def test_cli_reports_package_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.out == "pyveil 0.2.5\n"


def test_package_version_matches_project_metadata():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(
        r'^version = "([^"]+)"$',
        pyproject.read_text(encoding="utf-8"),
        re.MULTILINE,
    )

    assert match is not None
    assert __version__ == match.group(1)


def test_python_module_entrypoint_runs_demo():
    completed = subprocess.run(
        [sys.executable, "-m", "pyveil", "demo", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["counts_by_type"] == {"API_KEY": 1, "EMAIL": 1, "PHONE": 1}
    assert completed.stderr == ""
