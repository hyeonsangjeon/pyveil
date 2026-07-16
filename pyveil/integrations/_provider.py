"""Shared internals for remote provider integration templates."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from ..constants import Channel
from ..core import Veil

ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class RemoteSettingsValues:
    """Normalized values shared by OpenAI-compatible remote providers."""

    pyveil_secret: str = field(repr=False)
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    base_url: str | None = None
    pyveil_scope: str = "provider/example"
    max_tokens: int = 256
    timeout_seconds: float = 120.0


def load_remote_settings(
    *,
    provider_section: str,
    env_prefix: str,
    max_tokens_env: str,
    max_tokens_key: str,
    default_scope: str,
    extra_name: str,
    error_type: type[ValueError],
    config_path: Path | None,
    env_file: Path | None,
) -> RemoteSettingsValues:
    """Load a provider's environment, dotenv, and YAML settings."""

    if env_file is not None:
        _load_env_file(env_file, extra_name, error_type)
    config = _load_yaml(config_path, extra_name, error_type) if config_path else {}

    provider = _mapping_section(config, provider_section, error_type)
    pyveil = _mapping_section(config, "pyveil", error_type)
    _reject_plaintext_secret(provider, "api_key", provider_section + ".api_key_env", error_type)
    _reject_plaintext_secret(pyveil, "secret", "pyveil.secret_env", error_type)

    api_key_env = _env_name(
        _string_value(provider, "api_key_env", error_type) or env_prefix + "_API_KEY",
        error_type,
    )
    secret_env = _env_name(
        _string_value(pyveil, "secret_env", error_type) or "PYVEIL_SECRET",
        error_type,
    )
    pyveil_secret = _environment_or(secret_env, None)
    if not pyveil_secret:
        raise error_type(
            "pyveil HMAC secret is required; set "
            + secret_env
            + " in the environment or .env file"
        )

    base_url = _environment_or(
        env_prefix + "_BASE_URL",
        _string_value(provider, "base_url", error_type),
    )
    if base_url is not None:
        base_url = normalize_base_url(base_url, provider_section, error_type)

    return RemoteSettingsValues(
        pyveil_secret=pyveil_secret,
        api_key=_environment_or(api_key_env, None),
        model=_environment_or(
            env_prefix + "_MODEL",
            _string_value(provider, "model", error_type),
        ),
        base_url=base_url,
        pyveil_scope=_environment_or(
            "PYVEIL_SCOPE",
            _string_value(pyveil, "scope", error_type),
        )
        or default_scope,
        max_tokens=_int_setting(
            max_tokens_env,
            provider,
            max_tokens_key,
            256,
            1,
            1_000_000,
            error_type,
        ),
        timeout_seconds=_float_setting(
            env_prefix + "_TIMEOUT",
            provider,
            "timeout_seconds",
            120.0,
            1.0,
            3600.0,
            error_type,
        ),
    )


def validate_remote_settings(
    *,
    provider_name: str,
    model: str | None,
    base_url: str | None,
    pyveil_secret: str,
    max_tokens: int,
    max_tokens_name: str,
    timeout_seconds: float,
    error_type: type[ValueError],
) -> None:
    """Validate direct dataclass construction as well as loaded settings."""

    if not pyveil_secret:
        raise error_type("pyveil HMAC secret must not be empty")
    if model is not None and not model.strip():
        raise error_type(provider_name + " model must not be empty")
    if base_url is not None:
        normalize_base_url(base_url, provider_name, error_type)
    _validate_int(max_tokens_name, max_tokens, 1, 1_000_000, error_type)
    _validate_float("timeout_seconds", timeout_seconds, 1.0, 3600.0, error_type)


def normalize_base_url(
    base_url: str,
    provider_name: str,
    error_type: type[ValueError],
) -> str:
    """Validate a custom provider URL without allowing embedded credentials."""

    value = base_url.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise error_type(provider_name + " base_url must be an http or https URL")
    if parsed.username or parsed.password:
        raise error_type(provider_name + " base_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise error_type(provider_name + " base_url must not contain a query or fragment")
    return value.rstrip("/")


def redact_prompt(prompt: str, pyveil_secret: str, pyveil_scope: str) -> tuple[str, dict[str, int]]:
    """Return the exact text and finding counts allowed across a provider boundary."""

    veil = Veil.high(secret=pyveil_secret, scope=pyveil_scope)
    redaction = veil.redact_text(prompt, channel=Channel.PROMPT_INPUT)
    return redaction.text, dict(redaction.stats.counts_by_type)


def response_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def optional_int(value: Any, key: str) -> int | None:
    raw = response_value(value, key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


def optional_string(value: Any, key: str) -> str | None:
    raw = response_value(value, key)
    return raw if isinstance(raw, str) and raw else None


def prompt_from_args(
    prompt: str | None,
    prompt_file: Path | None,
    error_type: type[ValueError],
) -> str:
    if prompt_file is not None:
        if not prompt_file.is_file():
            raise error_type("prompt file does not exist: " + str(prompt_file))
        return prompt_file.read_text(encoding="utf-8")
    return prompt if prompt is not None else (
        "Write a one-sentence support follow-up for alice@example.com "
        "or 010-1234-5678."
    )


def format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(key + "=" + str(counts[key]) for key in sorted(counts))


def format_metrics(
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None = None,
) -> str:
    parts = []
    if input_tokens is not None:
        parts.append("input_tokens=" + str(input_tokens))
    if output_tokens is not None:
        parts.append("output_tokens=" + str(output_tokens))
    if total_tokens is not None:
        parts.append("total_tokens=" + str(total_tokens))
    return ", ".join(parts) if parts else "not reported"


def _load_env_file(
    path: Path,
    extra_name: str,
    error_type: type[ValueError],
) -> None:
    if not path.is_file():
        raise error_type("env file does not exist: " + str(path))
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise error_type('install .env support: pip install "pyveil[' + extra_name + ']"') from exc
    load_dotenv(dotenv_path=path, override=False)


def _load_yaml(
    path: Path,
    extra_name: str,
    error_type: type[ValueError],
) -> dict[str, Any]:
    if not path.is_file():
        raise error_type("YAML config does not exist: " + str(path))
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise error_type('install YAML support: pip install "pyveil[' + extra_name + ']"') from exc

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise error_type("YAML config must contain a top-level mapping")
    return parsed


def _mapping_section(
    config: Mapping[str, Any],
    name: str,
    error_type: type[ValueError],
) -> Mapping[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise error_type(name + " must be a YAML mapping")
    return value


def _string_value(
    section: Mapping[str, Any],
    key: str,
    error_type: type[ValueError],
) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise error_type(key + " must be a string")
    stripped = value.strip()
    return stripped or None


def _reject_plaintext_secret(
    section: Mapping[str, Any],
    key: str,
    replacement: str,
    error_type: type[ValueError],
) -> None:
    if key in section:
        raise error_type("do not store " + key + " in YAML; use " + replacement)


def _env_name(value: str, error_type: type[ValueError]) -> str:
    if not ENV_NAME_RE.fullmatch(value):
        raise error_type("invalid environment variable name: " + value)
    return value


def _environment_or(name: str, fallback: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return fallback
    stripped = value.strip()
    return stripped or fallback


def _int_setting(
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
    error_type: type[ValueError],
) -> int:
    raw: Any = os.environ.get(env_name, section.get(key, default))
    if isinstance(raw, bool):
        raise error_type(key + " must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise error_type(key + " must be an integer") from exc
    _validate_int(key, value, minimum, maximum, error_type)
    return value


def _float_setting(
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
    error_type: type[ValueError],
) -> float:
    raw: Any = os.environ.get(env_name, section.get(key, default))
    if isinstance(raw, bool):
        raise error_type(key + " must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise error_type(key + " must be a number") from exc
    _validate_float(key, value, minimum, maximum, error_type)
    return value


def _validate_int(
    name: str,
    value: int,
    minimum: int,
    maximum: int,
    error_type: type[ValueError],
) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise error_type(name + " must be between " + str(minimum) + " and " + str(maximum))


def _validate_float(
    name: str,
    value: float,
    minimum: float,
    maximum: float,
    error_type: type[ValueError],
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        raise error_type(name + " must be between " + str(minimum) + " and " + str(maximum))
