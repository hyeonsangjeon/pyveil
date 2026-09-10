"""Execute one configured local file redaction and persist its receipt."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import secrets
import shutil
import stat
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .constants import Channel
from .core import Veil
from .exceptions import BlockedSensitiveData
from .levels import Action, Level
from .run_config import ENV_NAME_RE, RunConfig, RunConfigError, load_run_config, parse_json

KEY_NAME = ".pyveil.key"
EXAMPLE_NAME = "input.example.json"
EXAMPLE_INPUT = {
    "source": "synthetic tutorial input; processed by the real redactor",
    "message": "Please contact tutorial.user@example.com about this ticket.",
    "headers": {"Authorization": "Bearer TUTORIAL_ONLY_NOT_A_CREDENTIAL"},
    "ticket": 42,
    "urgent": False,
}


class FileRunError(RuntimeError):
    """An input or output failure without raw input or secret values."""


@dataclass(frozen=True)
class FileRunResult:
    output: Path
    receipt: Path
    report: dict[str, Any]


def _write_private(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    complete = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        complete = True
    finally:
        if not complete:
            path.unlink()


def init_run_config(
    path: Path,
    *,
    input_path: str | None = None,
    input_format: str | None = None,
    example: bool = False,
    secret_env: str | None = None,
) -> None:
    """Create a ledger and optional private key/example, never overwriting files."""

    if path.suffix.lower() != ".json":
        raise RunConfigError(
            "use a .json run config; YAML reference schemas are no longer generated"
        )
    if secret_env is not None and ENV_NAME_RE.fullmatch(secret_env) is None:
        raise RunConfigError("secret_env must be an environment variable name")
    if example and input_path is not None:
        raise RunConfigError("--example and --input cannot be combined")
    if example and input_format not in (None, "json"):
        raise RunConfigError("--example creates JSON input")
    parent = path.resolve().parent
    input_name = EXAMPLE_NAME if example else (input_path or "input.txt")
    selected_format = input_format or (
        "json" if Path(input_name).suffix.lower() == ".json" else "text"
    )
    if selected_format not in {"text", "json"}:
        raise RunConfigError("input_format must be text or json")
    config = {
        "schema_version": 1,
        "pyveil_version": __version__,
        "input": input_name,
        "input_format": selected_format,
        "input_origin": "synthetic" if example else "user-provided",
        "output_dir": ".pyveil-runs",
        "scope": "local/files",
        "channel": Channel.PROMPT_INPUT.value,
        "level": Level.HIGH.value,
        "max_input_chars": 1_000_000,
        "actions": {},
    }
    new_files = []
    if secret_env is not None:
        config["secret_env"] = secret_env
    else:
        config["secret_file"] = KEY_NAME
        new_files.append((parent / KEY_NAME, secrets.token_hex(32) + "\n"))
    if example:
        new_files.append((parent / EXAMPLE_NAME, json.dumps(EXAMPLE_INPUT, indent=2) + "\n"))
    new_files.append((path, json.dumps(config, indent=2) + "\n"))
    if len({target.resolve() for target, _ in new_files}) != len(new_files):
        raise RunConfigError("config, example, and secret paths must be distinct")
    if not example and (parent / input_name).resolve() in {
        target.resolve() for target, _ in new_files
    }:
        raise RunConfigError("input must not be the config or secret file")
    created: list[Path] = []
    complete = False
    try:
        for target, _ in new_files:
            if target.exists() or target.is_symlink():
                raise RunConfigError(
                    "init would overwrite a file; use a new directory or --secret-env with a new config"
                )
        for target, content in new_files:
            _write_private(target, content)
            created.append(target)
        load_run_config(path)
        complete = True
    except OSError as exc:
        raise FileRunError("cannot initialize files; check the directory and permissions") from exc
    finally:
        if not complete:
            for target in reversed(created):
                target.unlink()


def _load_secret(config: RunConfig) -> bytes:
    if config.secret_env is not None:
        value = os.environ.get(config.secret_env)
        if not value:
            raise RunConfigError("the environment variable named by secret_env is missing or empty")
        try:
            return value.encode("utf-8")
        except UnicodeError as exc:
            raise RunConfigError(
                "the secret environment variable must contain valid Unicode"
            ) from exc
    path = config.secret_file
    if path is None:
        raise RunConfigError("secret_file is missing")
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise RunConfigError("secret_file must be a regular file")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
            raise RunConfigError("secret_file must be private; run chmod 600 on that file")
        with path.open("rb") as handle:
            value_bytes = handle.read(4097)
    except OSError as exc:
        raise RunConfigError("cannot read secret_file; restore the original private key") from exc
    if not value_bytes or len(value_bytes) > 4096:
        raise RunConfigError("secret_file must contain 1 to 4096 bytes")
    if not value_bytes.strip():
        raise RunConfigError("secret_file must not be empty or whitespace-only")
    return value_bytes.strip()


def _read_input(config: RunConfig) -> str:
    try:
        if not config.input_path.is_file():
            raise FileRunError("input is not a regular file; check the path relative to the config")
        with config.input_path.open(encoding="utf-8", newline="") as handle:
            text = handle.read(config.max_input_chars + 1)
    except (OSError, UnicodeError) as exc:
        raise FileRunError("cannot read input as UTF-8; check the file and permissions") from exc
    if len(text) > config.max_input_chars:
        raise RunConfigError("input exceeds configured max_input_chars")
    return text


def run_file(path: Path) -> FileRunResult:
    """Run the installed engine; success is published only after both files exist."""

    started = time.perf_counter()
    config = load_run_config(path)
    secret = _load_secret(config)
    text = _read_input(config)
    policy = config.policy()
    veil = Veil(
        secret=secret,
        scope=config.scope,
        policy=policy,
        max_input_chars=config.max_input_chars,
    )
    try:
        if config.input_format == "json":
            try:
                value = parse_json(text)
            except ValueError as exc:
                raise FileRunError(
                    "input must be valid JSON with unique keys and finite numbers"
                ) from exc
            if not isinstance(value, (dict, list)):
                raise FileRunError("JSON input must be an object or array")
            result = veil.redact_data(value, channel=config.channel)
            output_text = (
                json.dumps(result.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
        else:
            result = veil.redact_text(text, channel=config.channel)
            output_text = result.text
        output_bytes = output_text.encode("utf-8")
    except BlockedSensitiveData:
        raise
    except RecursionError as exc:
        raise FileRunError("input nesting is too deep; reduce the JSON nesting") from exc
    except UnicodeError as exc:
        raise FileRunError("input contains invalid Unicode") from exc
    except ValueError as exc:
        raise RunConfigError("input exceeds redaction limits") from exc
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex
    output_name = "redacted.json" if config.input_format == "json" else "redacted.txt"
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "completed",
        "pyveil_version": __version__,
        "python_version": platform.python_version(),
        "execution": {
            "kind": "local-file-redaction",
            "measured": True,
            "input_origin": config.input_origin,
            "provider_called": False,
            "network": "none",
        },
        "config_sha256": config.sha256,
        "input_hmac_sha256": hmac.new(
            secret, b"pyveil/file-run/input\x00" + text.encode("utf-8"), hashlib.sha256
        ).hexdigest(),
        "key_id": hmac.new(secret, b"pyveil/file-run/key-id", hashlib.sha256).hexdigest()[:16],
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "output_file": output_name,
        "output_bytes": len(output_bytes),
        "input_chars": len(text),
        "channel": config.channel.value,
        "level": config.level.value,
        "max_input_chars": config.max_input_chars,
        "findings": {
            "total": result.stats.total_findings,
            "by_type": dict(sorted(result.stats.counts_by_type.items())),
            "redacted": sum(
                policy.action_for(config.channel, f.type) == Action.REDACT for f in result.findings
            ),
            "passed": sum(
                policy.action_for(config.channel, f.type) == Action.PASS for f in result.findings
            ),
        },
        "processing_seconds": round(time.perf_counter() - started, 6),
    }
    staging: Path | None = None
    try:
        config.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=config.output_dir))
        _write_private(staging / output_name, output_text)
        _write_private(
            staging / "receipt.json", json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        destination = config.output_dir / run_id
        staging.rename(destination)
        staging = None
    except OSError as exc:
        raise FileRunError(
            "cannot persist run output; check output_dir permissions and free space"
        ) from exc
    finally:
        if staging is not None:
            shutil.rmtree(staging)
    return FileRunResult(
        output=destination / output_name,
        receipt=destination / "receipt.json",
        report=report,
    )
