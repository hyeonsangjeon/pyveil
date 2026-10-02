"""Measure a clean install and real file processing against a 300-second budget.

Build first, then use --wheel dist/pyveil-VERSION-py3-none-any.whl.
Use --version VERSION after publication to install from the public PyPI index.
No mocks, provider requests, or fixed HMAC keys are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.documentation_checks import quickstart_code  # noqa: E402


def verify_install(wheel: Path | None, version: str | None) -> dict[str, Any]:
    started = time.perf_counter()
    deadline = started + 300

    def execute(command: list[str], cwd: Path, expected: int = 0) -> str:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise RuntimeError("five-minute budget exceeded")
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=remaining,
        )
        if completed.returncode != expected:
            raise RuntimeError(
                f"first-run step failed with exit {completed.returncode} (expected {expected}): "
                + completed.stderr[-2000:]
            )
        return completed.stdout

    with tempfile.TemporaryDirectory(prefix="pyveil-first-run-") as directory:
        workspace = Path(directory)
        environment = workspace / "venv"
        execute([sys.executable, "-m", "venv", str(environment)], workspace)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = [str(python), "-I", "-m", "pyveil"]
        pip = [
            str(python),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            "--no-cache-dir",
        ]
        if wheel is not None:
            execute([*pip, "--no-index", str(wheel.resolve())], workspace)
        else:
            execute(
                [
                    *pip,
                    "--index-url",
                    "https://pypi.org/simple",
                    "--only-binary=:all:",
                    "pyveil==" + str(version),
                ],
                workspace,
            )
        installed = execute(
            [
                str(python),
                "-I",
                "-c",
                "import pyveil; print(pyveil.__file__); print(pyveil.__version__)",
            ],
            workspace,
        ).splitlines()
        if environment.resolve() not in Path(installed[0]).resolve().parents:
            raise RuntimeError("source checkout shadowed the installed distribution")
        install_seconds = time.perf_counter() - started
        snippet = quickstart_code()
        quickstart_output = execute([str(python), "-I", "-c", snippet], workspace)
        if not re.fullmatch(r"Email \[EMAIL:[0-9a-f]{12}\] about ticket 42\.\n", quickstart_output):
            raise RuntimeError("installed README quickstart did not produce the documented shape")
        for example in ("openai_agents_guardrail.py", "litellm_proxy_filter.py"):
            output = execute([str(python), "-I", str(ROOT / "examples" / example)], workspace)
            if "alice@example.com" in output or "[EMAIL:" not in output or "skipped" not in output:
                raise RuntimeError("keyless integration recipe contract failed")
        execute([*command, "init", "--example"], workspace)
        config = workspace / "pyveil.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        source = workspace / data["input"]
        original = source.read_bytes()
        key = (workspace / data["secret_file"]).read_text(encoding="utf-8").strip()
        execute([*command, "test-config"], workspace)

        first_locations = json.loads(execute([*command, "run", "--format", "json"], workspace))
        first = Path(first_locations["output"])
        receipt = json.loads(Path(first_locations["receipt"]).read_text(encoding="utf-8"))
        first_result_seconds = time.perf_counter() - started
        another_cwd = workspace / "different-working-directory"
        another_cwd.mkdir()
        second_locations = json.loads(
            execute([*command, "run", str(config), "--format", "json"], another_cwd)
        )
        second = Path(second_locations["output"])
        second_receipt = json.loads(Path(second_locations["receipt"]).read_text(encoding="utf-8"))

        payload = json.loads(first.read_text(encoding="utf-8"))
        if (
            first == second
            or first.read_bytes() != second.read_bytes()
            or source.read_bytes() != original
            or payload["ticket"] != 42
            or payload["urgent"] is not False
            or receipt["findings"]["by_type"] != {"AUTH_HEADER": 1, "EMAIL": 1}
            or receipt["output_sha256"] != hashlib.sha256(first.read_bytes()).hexdigest()
            or receipt["config_sha256"] != hashlib.sha256(config.read_bytes()).hexdigest()
            or receipt["input_hmac_sha256"] != second_receipt["input_hmac_sha256"]
        ):
            raise RuntimeError("file processing or reproducibility contract failed")
        for private in ("tutorial.user@example.com", "TUTORIAL_ONLY_NOT_A_CREDENTIAL", key):
            if private in first.read_text(encoding="utf-8") or private in json.dumps(receipt):
                raise RuntimeError("a labeled tutorial value or key survived in the output/receipt")
        if receipt["execution"] != {
            "kind": "local-file-redaction",
            "measured": True,
            "input_origin": "synthetic",
            "provider_called": False,
            "network": "none",
        }:
            raise RuntimeError("execution provenance is missing or incorrect")

        runs = workspace / data["output_dir"]
        before_block = set(runs.iterdir())
        data["channel"] = "tool.call.arguments"
        config.write_text(json.dumps(data), encoding="utf-8")
        execute([*command, "run"], workspace, expected=2)
        if set(runs.iterdir()) != before_block:
            raise RuntimeError("blocked execution published an output")
        data["channel"] = "prompt.intput"
        config.write_text(json.dumps(data), encoding="utf-8")
        execute([*command, "test-config"], workspace, expected=2)
        elapsed = time.perf_counter() - started
        if elapsed >= 300:
            raise RuntimeError("five-minute budget exceeded")
        return {
            "status": "passed",
            "pyveil_version": installed[1],
            "python_version": platform.python_version(),
            "system": platform.system(),
            "installation_source": "local-wheel" if wheel is not None else "pypi",
            "install_seconds": round(install_seconds, 3),
            "install_to_first_result_seconds": round(first_result_seconds, 3),
            "install_and_all_checks_seconds": round(elapsed, 3),
            "budget_seconds": 300,
            "execution": "real-local-file-redaction",
            "input_origin": "synthetic",
            "provider_called": False,
            "identical_outputs": True,
            "input_unchanged": True,
            "blocked_run_wrote_nothing": True,
            "config_errors_fail": True,
            "readme_quickstart_passed": True,
            "keyless_checkout_recipes_passed": True,
            "output_sha256": receipt["output_sha256"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--wheel", type=Path)
    target.add_argument("--version")
    args = parser.parse_args()
    report = verify_install(args.wheel, args.version)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
