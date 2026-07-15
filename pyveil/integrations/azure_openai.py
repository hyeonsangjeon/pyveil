"""Redact a prompt before sending it to Azure OpenAI.

Install the optional example dependencies:

    pip install "pyveil[azure-openai]"

Try the boundary without an Azure request:

    PYVEIL_SECRET=local-demo-secret \
      python -m pyveil.integrations.azure_openai --dry-run

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

from ..constants import Channel
from ..core import Veil

__all__ = [
    "AzureCallResult",
    "AzureOpenAISettings",
    "ConfigError",
    "ask_azure_openai",
    "load_settings",
    "redact_for_azure",
]

DEFAULT_PROMPT = "Write a one-sentence support follow-up for alice@example.com " "or 010-1234-5678."
DEFAULT_SCOPE = "azure-openai/example"
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(ValueError):
    """Raised when the example configuration is missing or unsafe."""


@dataclass(frozen=True)
class AzureOpenAISettings:
    """Runtime settings resolved from environment variables and YAML."""

    endpoint: str | None
    deployment: str | None
    api_key: str | None = field(repr=False)
    pyveil_secret: str = field(repr=False)
    pyveil_scope: str = DEFAULT_SCOPE

    @property
    def base_url(self) -> str:
        if not self.endpoint:
            raise ConfigError("AZURE_OPENAI_ENDPOINT is required for a live request")
        return self.endpoint.rstrip("/") + "/openai/v1/"

    def validate_live(self) -> None:
        missing = []
        if not self.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        if not self.api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if missing:
            raise ConfigError("missing live Azure settings: " + ", ".join(missing))


@dataclass(frozen=True)
class AzureCallResult:
    """Safe request details and the optional provider response."""

    redacted_input: str
    finding_counts: Mapping[str, int]
    output_text: str | None = None


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    require_azure: bool = True,
) -> AzureOpenAISettings:
    """Load settings from an optional .env file, YAML, and the environment.

    Process environment variables have the highest priority. ``.env`` only
    fills variables that are currently absent. YAML can hold endpoint,
    deployment, and scope, but secret values must stay in environment
    variables referenced by ``api_key_env`` and ``secret_env``.
    """

    if env_file is not None:
        _load_env_file(env_file)
    config = _load_yaml(config_path) if config_path is not None else {}

    azure = _mapping_section(config, "azure_openai")
    pyveil = _mapping_section(config, "pyveil")
    _reject_plaintext_secret(azure, "api_key", "azure_openai.api_key_env")
    _reject_plaintext_secret(pyveil, "secret", "pyveil.secret_env")

    api_key_env = _env_name(_string_value(azure, "api_key_env") or "AZURE_OPENAI_API_KEY")
    secret_env = _env_name(_string_value(pyveil, "secret_env") or "PYVEIL_SECRET")

    endpoint = _environment_or("AZURE_OPENAI_ENDPOINT", _string_value(azure, "endpoint"))
    deployment = _environment_or("AZURE_OPENAI_DEPLOYMENT", _string_value(azure, "deployment"))
    api_key = _environment_or(api_key_env, None)
    pyveil_secret = _environment_or(secret_env, None)
    scope = _environment_or("PYVEIL_SCOPE", _string_value(pyveil, "scope")) or DEFAULT_SCOPE

    if not pyveil_secret:
        raise ConfigError(
            "pyveil HMAC secret is required; set " + secret_env + " in the environment or .env file"
        )

    settings = AzureOpenAISettings(
        endpoint=endpoint,
        deployment=deployment,
        api_key=api_key,
        pyveil_secret=pyveil_secret,
        pyveil_scope=scope,
    )
    if require_azure:
        settings.validate_live()
    return settings


def redact_for_azure(prompt: str, settings: AzureOpenAISettings) -> AzureCallResult:
    """Return exactly what may cross the Azure OpenAI boundary."""

    veil = Veil.high(secret=settings.pyveil_secret, scope=settings.pyveil_scope)
    redaction = veil.redact_text(prompt, channel=Channel.PROMPT_INPUT)
    return AzureCallResult(
        redacted_input=redaction.text,
        finding_counts=dict(redaction.stats.counts_by_type),
    )


def ask_azure_openai(
    prompt: str,
    settings: AzureOpenAISettings,
    client: Any | None = None,
) -> AzureCallResult:
    """Redact ``prompt``, call Azure OpenAI, and return safe request metadata."""

    settings.validate_live()
    safe = redact_for_azure(prompt, settings)
    azure_client = client if client is not None else _build_client(settings)
    response = azure_client.responses.create(
        model=settings.deployment,
        input=safe.redacted_input,
    )
    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str):
        raise RuntimeError("Azure OpenAI response did not include output_text")
    return AzureCallResult(
        redacted_input=safe.redacted_input,
        finding_counts=safe.finding_counts,
        output_text=output_text,
    )


def _build_client(settings: AzureOpenAISettings) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ConfigError(
            'install the Azure example dependencies: pip install "pyveil[azure-openai]"'
        ) from exc

    return OpenAI(api_key=settings.api_key, base_url=settings.base_url)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        raise ConfigError("env file does not exist: " + str(path))
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ConfigError('install .env support: pip install "pyveil[azure-openai]"') from exc
    load_dotenv(dotenv_path=path, override=False)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError("YAML config does not exist: " + str(path))
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ConfigError('install YAML support: pip install "pyveil[azure-openai]"') from exc

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError("YAML config must contain a top-level mapping")
    return parsed


def _mapping_section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(name + " must be a YAML mapping")
    return value


def _string_value(section: Mapping[str, Any], key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(key + " must be a string")
    stripped = value.strip()
    return stripped or None


def _reject_plaintext_secret(section: Mapping[str, Any], key: str, replacement: str) -> None:
    if key in section:
        raise ConfigError("do not store " + key + " in YAML; use " + replacement)


def _env_name(value: str) -> str:
    if not ENV_NAME_RE.fullmatch(value):
        raise ConfigError("invalid environment variable name: " + value)
    return value


def _environment_or(name: str, fallback: str | None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return fallback
    stripped = value.strip()
    return stripped or fallback


def _prompt_from_args(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt_file is not None:
        if not prompt_file.is_file():
            raise ConfigError("prompt file does not exist: " + str(prompt_file))
        return prompt_file.read_text(encoding="utf-8")
    return prompt if prompt is not None else DEFAULT_PROMPT


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(key + "=" + str(counts[key]) for key in sorted(counts))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="YAML settings file")
    parser.add_argument("--env-file", type=Path, help="Optional dotenv file, usually .env")
    parser.add_argument("--dry-run", action="store_true", help="Redact without calling Azure")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Prompt text; the default is synthetic")
    prompt_group.add_argument("--prompt-file", type=Path, help="Read prompt text from a file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        prompt = _prompt_from_args(args.prompt, args.prompt_file)
        settings = load_settings(
            config_path=args.config,
            env_file=args.env_file,
            require_azure=not args.dry_run,
        )
        result = (
            redact_for_azure(prompt, settings)
            if args.dry_run
            else ask_azure_openai(prompt, settings)
        )
    except ConfigError as exc:
        print("configuration error: " + str(exc), file=sys.stderr)
        return 2

    print("mode: " + ("dry-run" if args.dry_run else "live"))
    print("deployment: " + (settings.deployment or "not configured"))
    print("sent-to-azure: " + result.redacted_input)
    print("findings: " + _format_counts(result.finding_counts))
    if result.output_text is None:
        print("azure-response: skipped (--dry-run)")
    else:
        print("azure-response: " + result.output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
