"""Redact a prompt before sending it to a local Ollama model.

Install the optional integration dependencies and pull a model:

    pip install "pyveil[ollama]"
    ollama pull qwen3.5:4b

Prove the boundary without loading a model:

    PYVEIL_SECRET=local-demo-secret \
      python -m pyveil.integrations.ollama --dry-run

For a live request, configure environment variables directly or combine a
YAML file with secrets from the environment. Environment variables override
non-secret YAML settings.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from ..constants import Channel
from ..core import Veil

__all__ = [
    "OllamaCallError",
    "OllamaCallResult",
    "OllamaConfigError",
    "OllamaSettings",
    "ask_ollama",
    "load_settings",
    "redact_for_ollama",
]

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_PROMPT = "Write a one-sentence support follow-up for alice@example.com " "or 010-1234-5678."
DEFAULT_SCOPE = "ollama/example"
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class OllamaConfigError(ValueError):
    """Raised when the Ollama integration configuration is invalid."""


class OllamaCallError(RuntimeError):
    """Raised when a safe Ollama request cannot be completed."""


@dataclass(frozen=True)
class OllamaSettings:
    """Runtime settings resolved from environment variables and YAML."""

    pyveil_secret: str = field(repr=False)
    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    pyveil_scope: str = DEFAULT_SCOPE
    num_ctx: int = 4096
    num_predict: int = 128
    temperature: float = 0.2
    keep_alive: str = "0"
    timeout_seconds: float = 120.0

    def validate(self) -> None:
        _normalize_host(self.host)
        if not self.model.strip():
            raise OllamaConfigError("Ollama model must not be empty")
        if not self.pyveil_secret:
            raise OllamaConfigError("pyveil HMAC secret must not be empty")
        _validate_int("num_ctx", self.num_ctx, minimum=512, maximum=262_144)
        _validate_int("num_predict", self.num_predict, minimum=1, maximum=4096)
        _validate_float("temperature", self.temperature, minimum=0.0, maximum=2.0)
        _validate_float("timeout_seconds", self.timeout_seconds, minimum=1.0, maximum=3600.0)
        if not self.keep_alive.strip():
            raise OllamaConfigError("keep_alive must not be empty")


@dataclass(frozen=True)
class OllamaCallResult:
    """Safe request details, provider response, and optional timing metrics."""

    redacted_input: str
    finding_counts: Mapping[str, int]
    output_text: str | None = None
    total_duration_ms: float | None = None
    load_duration_ms: float | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
) -> OllamaSettings:
    """Load settings from an optional .env file, YAML, and the environment.

    Process environment variables have the highest priority. ``.env`` only
    fills variables that are currently absent. YAML can hold non-secret
    runtime settings, while the pyveil HMAC secret must stay in an environment
    variable referenced by ``secret_env``.
    """

    if env_file is not None:
        _load_env_file(env_file)
    config = _load_yaml(config_path) if config_path is not None else {}

    ollama = _mapping_section(config, "ollama")
    pyveil = _mapping_section(config, "pyveil")
    _reject_plaintext_secret(pyveil, "secret", "pyveil.secret_env")

    secret_env = _env_name(_string_value(pyveil, "secret_env") or "PYVEIL_SECRET")
    pyveil_secret = _environment_or(secret_env, None)
    if not pyveil_secret:
        raise OllamaConfigError(
            "pyveil HMAC secret is required; set " + secret_env + " in the environment or .env file"
        )

    settings = OllamaSettings(
        pyveil_secret=pyveil_secret,
        host=_normalize_host(
            _string_setting("OLLAMA_HOST", ollama, "host", DEFAULT_HOST)
        ),
        model=_string_setting("OLLAMA_MODEL", ollama, "model", DEFAULT_MODEL),
        pyveil_scope=_environment_or("PYVEIL_SCOPE", _string_value(pyveil, "scope"))
        or DEFAULT_SCOPE,
        num_ctx=_int_setting("OLLAMA_NUM_CTX", ollama, "num_ctx", 4096, 512, 262_144),
        num_predict=_int_setting(
            "OLLAMA_NUM_PREDICT", ollama, "num_predict", 128, 1, 4096
        ),
        temperature=_float_setting(
            "OLLAMA_TEMPERATURE", ollama, "temperature", 0.2, 0.0, 2.0
        ),
        keep_alive=_keep_alive_setting(ollama),
        timeout_seconds=_float_setting(
            "OLLAMA_TIMEOUT", ollama, "timeout_seconds", 120.0, 1.0, 3600.0
        ),
    )
    settings.validate()
    return settings


def redact_for_ollama(prompt: str, settings: OllamaSettings) -> OllamaCallResult:
    """Return exactly what may cross the Ollama client boundary."""

    settings.validate()
    veil = Veil.high(secret=settings.pyveil_secret, scope=settings.pyveil_scope)
    redaction = veil.redact_text(prompt, channel=Channel.PROMPT_INPUT)
    return OllamaCallResult(
        redacted_input=redaction.text,
        finding_counts=dict(redaction.stats.counts_by_type),
    )


def ask_ollama(
    prompt: str,
    settings: OllamaSettings,
    client: Any | None = None,
) -> OllamaCallResult:
    """Redact ``prompt``, call Ollama, and return safe request metadata."""

    safe = redact_for_ollama(prompt, settings)
    ollama_client = client if client is not None else _build_client(settings)
    try:
        response = ollama_client.chat(
            model=settings.model,
            messages=[{"role": "user", "content": safe.redacted_input}],
            stream=False,
            think=False,
            options={
                "num_ctx": settings.num_ctx,
                "num_predict": settings.num_predict,
                "temperature": settings.temperature,
            },
            keep_alive=settings.keep_alive,
        )
    except Exception as exc:
        raise OllamaCallError(
            "Ollama request failed; verify that the server is running and the model is available"
        ) from exc

    message = _response_value(response, "message")
    output_text = _response_value(message, "content")
    if not isinstance(output_text, str) or not output_text.strip():
        raise OllamaCallError("Ollama response did not include message.content")

    return OllamaCallResult(
        redacted_input=safe.redacted_input,
        finding_counts=safe.finding_counts,
        output_text=output_text,
        total_duration_ms=_duration_ms(_optional_int(response, "total_duration")),
        load_duration_ms=_duration_ms(_optional_int(response, "load_duration")),
        prompt_eval_count=_optional_int(response, "prompt_eval_count"),
        eval_count=_optional_int(response, "eval_count"),
    )


def _build_client(settings: OllamaSettings) -> Any:
    try:
        from ollama import Client
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise OllamaConfigError(
            'install the Ollama integration dependencies: pip install "pyveil[ollama]"'
        ) from exc

    return Client(host=settings.host, timeout=settings.timeout_seconds)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        raise OllamaConfigError("env file does not exist: " + str(path))
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise OllamaConfigError('install .env support: pip install "pyveil[ollama]"') from exc
    load_dotenv(dotenv_path=path, override=False)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OllamaConfigError("YAML config does not exist: " + str(path))
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise OllamaConfigError('install YAML support: pip install "pyveil[ollama]"') from exc

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise OllamaConfigError("YAML config must contain a top-level mapping")
    return parsed


def _mapping_section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise OllamaConfigError(name + " must be a YAML mapping")
    return value


def _string_value(section: Mapping[str, Any], key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise OllamaConfigError(key + " must be a string")
    stripped = value.strip()
    return stripped or None


def _string_setting(
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: str,
) -> str:
    value = _environment_or(env_name, _string_value(section, key)) or default
    if not value.strip():
        raise OllamaConfigError(key + " must not be empty")
    return value


def _int_setting(
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw: Any = os.environ.get(env_name, section.get(key, default))
    if isinstance(raw, bool):
        raise OllamaConfigError(key + " must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise OllamaConfigError(key + " must be an integer") from exc
    _validate_int(key, value, minimum, maximum)
    return value


def _keep_alive_setting(section: Mapping[str, Any]) -> str:
    raw: Any = os.environ.get("OLLAMA_KEEP_ALIVE", section.get("keep_alive", "0"))
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise OllamaConfigError("keep_alive must be a duration string or number")
    value = str(raw).strip()
    if not value:
        raise OllamaConfigError("keep_alive must not be empty")
    return value


def _float_setting(
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw: Any = os.environ.get(env_name, section.get(key, default))
    if isinstance(raw, bool):
        raise OllamaConfigError(key + " must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise OllamaConfigError(key + " must be a number") from exc
    _validate_float(key, value, minimum, maximum)
    return value


def _validate_int(name: str, value: int, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not minimum <= value <= maximum:
        raise OllamaConfigError(
            name + " must be between " + str(minimum) + " and " + str(maximum)
        )


def _validate_float(name: str, value: float, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not minimum <= value <= maximum:
        raise OllamaConfigError(
            name + " must be between " + str(minimum) + " and " + str(maximum)
        )


def _normalize_host(host: str) -> str:
    value = host.strip()
    if "://" not in value:
        value = "http://" + value
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise OllamaConfigError("Ollama host must be an http or https URL")
    if parsed.username or parsed.password:
        raise OllamaConfigError("Ollama host must not contain credentials")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise OllamaConfigError("Ollama host must not contain a path, query, or fragment")
    return value.rstrip("/")


def _reject_plaintext_secret(section: Mapping[str, Any], key: str, replacement: str) -> None:
    if key in section:
        raise OllamaConfigError("do not store " + key + " in YAML; use " + replacement)


def _env_name(value: str) -> str:
    if not ENV_NAME_RE.fullmatch(value):
        raise OllamaConfigError("invalid environment variable name: " + value)
    return value


def _environment_or(name: str, fallback: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return fallback
    stripped = value.strip()
    return stripped or fallback


def _response_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _optional_int(value: Any, key: str) -> int | None:
    raw = _response_value(value, key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


def _duration_ms(nanoseconds: int | None) -> float | None:
    if nanoseconds is None:
        return None
    return round(nanoseconds / 1_000_000, 3)


def _prompt_from_args(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt_file is not None:
        if not prompt_file.is_file():
            raise OllamaConfigError("prompt file does not exist: " + str(prompt_file))
        return prompt_file.read_text(encoding="utf-8")
    return prompt if prompt is not None else DEFAULT_PROMPT


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(key + "=" + str(counts[key]) for key in sorted(counts))


def _format_metrics(result: OllamaCallResult) -> str:
    parts = []
    if result.total_duration_ms is not None:
        parts.append("total_ms=" + str(result.total_duration_ms))
    if result.load_duration_ms is not None:
        parts.append("load_ms=" + str(result.load_duration_ms))
    if result.prompt_eval_count is not None:
        parts.append("prompt_tokens=" + str(result.prompt_eval_count))
    if result.eval_count is not None:
        parts.append("output_tokens=" + str(result.eval_count))
    return ", ".join(parts) if parts else "not reported"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="YAML settings file")
    parser.add_argument("--env-file", type=Path, help="Optional dotenv file, usually .env")
    parser.add_argument("--dry-run", action="store_true", help="Redact without calling Ollama")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Prompt text; the default is synthetic")
    prompt_group.add_argument("--prompt-file", type=Path, help="Read prompt text from a file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        prompt = _prompt_from_args(args.prompt, args.prompt_file)
        settings = load_settings(config_path=args.config, env_file=args.env_file)
        result = (
            redact_for_ollama(prompt, settings)
            if args.dry_run
            else ask_ollama(prompt, settings)
        )
    except OllamaConfigError as exc:
        print("configuration error: " + str(exc), file=sys.stderr)
        return 2
    except OllamaCallError as exc:
        print("ollama error: " + str(exc), file=sys.stderr)
        return 3

    print("mode: " + ("dry-run" if args.dry_run else "live"))
    print("model: " + settings.model)
    print("host: " + settings.host)
    print("sent-to-ollama: " + result.redacted_input)
    print("findings: " + _format_counts(result.finding_counts))
    if result.output_text is None:
        print("ollama-response: skipped (--dry-run)")
    else:
        print("ollama-response: " + result.output_text)
        print("metrics: " + _format_metrics(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
