"""Redact a prompt before sending it to the OpenAI Responses API.

Install the optional integration dependencies:

    pip install "pyveil[openai]"

Prove the boundary without an API key or network request:

    PYVEIL_SECRET=local-demo-secret \
      python -m pyveil.integrations.openai --dry-run

For a live request, configure environment variables directly or combine a
YAML file with secrets from the environment. Environment variables override
non-secret YAML settings.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._provider import (
    format_counts,
    format_metrics,
    load_remote_settings,
    normalize_base_url,
    optional_int,
    optional_string,
    prompt_from_args,
    redact_prompt,
    response_value,
    validate_remote_settings,
)

__all__ = [
    "OpenAICallError",
    "OpenAICallResult",
    "OpenAIConfigError",
    "OpenAISettings",
    "ask_openai",
    "load_settings",
    "redact_for_openai",
]

DEFAULT_SCOPE = "openai/example"


class OpenAIConfigError(ValueError):
    """Raised when the OpenAI integration configuration is invalid."""


class OpenAICallError(RuntimeError):
    """Raised when a safe OpenAI request cannot be completed."""


@dataclass(frozen=True)
class OpenAISettings:
    """Runtime settings resolved from environment variables and YAML."""

    pyveil_secret: str = field(repr=False)
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    base_url: str | None = None
    pyveil_scope: str = DEFAULT_SCOPE
    max_output_tokens: int = 256
    timeout_seconds: float = 120.0

    def validate(self) -> None:
        validate_remote_settings(
            provider_name="OpenAI",
            model=self.model,
            base_url=self.base_url,
            pyveil_secret=self.pyveil_secret,
            max_tokens=self.max_output_tokens,
            max_tokens_name="max_output_tokens",
            timeout_seconds=self.timeout_seconds,
            error_type=OpenAIConfigError,
        )

    def validate_live(self) -> None:
        self.validate()
        missing = []
        if not self.model:
            missing.append("OPENAI_MODEL")
        if not self.api_key:
            missing.append("OPENAI_API_KEY")
        if missing:
            raise OpenAIConfigError("missing live OpenAI settings: " + ", ".join(missing))


@dataclass(frozen=True)
class OpenAICallResult:
    """Safe request details, provider response, and optional usage metrics."""

    redacted_input: str
    finding_counts: Mapping[str, int]
    output_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    request_id: str | None = None


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    require_openai: bool = True,
) -> OpenAISettings:
    """Load process environment, optional dotenv, and non-secret YAML settings."""

    values = load_remote_settings(
        provider_section="openai",
        env_prefix="OPENAI",
        max_tokens_env="OPENAI_MAX_OUTPUT_TOKENS",
        max_tokens_key="max_output_tokens",
        default_scope=DEFAULT_SCOPE,
        extra_name="openai",
        error_type=OpenAIConfigError,
        config_path=config_path,
        env_file=env_file,
    )
    settings = OpenAISettings(
        pyveil_secret=values.pyveil_secret,
        api_key=values.api_key,
        model=values.model,
        base_url=values.base_url,
        pyveil_scope=values.pyveil_scope,
        max_output_tokens=values.max_tokens,
        timeout_seconds=values.timeout_seconds,
    )
    if require_openai:
        settings.validate_live()
    else:
        settings.validate()
    return settings


def redact_for_openai(prompt: str, settings: OpenAISettings) -> OpenAICallResult:
    """Return exactly what may cross the OpenAI SDK boundary."""

    settings.validate()
    text, counts = redact_prompt(prompt, settings.pyveil_secret, settings.pyveil_scope)
    return OpenAICallResult(redacted_input=text, finding_counts=counts)


def ask_openai(
    prompt: str,
    settings: OpenAISettings,
    client: Any | None = None,
) -> OpenAICallResult:
    """Redact ``prompt``, call the Responses API, and return safe metadata."""

    settings.validate_live()
    safe = redact_for_openai(prompt, settings)
    openai_client = client if client is not None else _build_client(settings)
    try:
        response = openai_client.responses.create(
            model=settings.model,
            input=safe.redacted_input,
            max_output_tokens=settings.max_output_tokens,
        )
    except Exception as exc:
        raise OpenAICallError(
            "OpenAI request failed; verify credentials, model access, and network connectivity"
        ) from exc

    output_text = response_value(response, "output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise OpenAICallError("OpenAI response did not include output_text")

    usage = response_value(response, "usage")
    return OpenAICallResult(
        redacted_input=safe.redacted_input,
        finding_counts=safe.finding_counts,
        output_text=output_text,
        input_tokens=optional_int(usage, "input_tokens"),
        output_tokens=optional_int(usage, "output_tokens"),
        total_tokens=optional_int(usage, "total_tokens"),
        request_id=optional_string(response, "_request_id"),
    )


def _build_client(settings: OpenAISettings) -> Any:
    if sys.version_info < (3, 9):  # pragma: no cover - integration SDK boundary
        raise OpenAIConfigError("the official OpenAI Python SDK requires Python 3.9+")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise OpenAIConfigError(
            'install the OpenAI integration dependencies: pip install "pyveil[openai]"'
        ) from exc

    kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_seconds,
    }
    if settings.base_url:
        kwargs["base_url"] = normalize_base_url(
            settings.base_url,
            "OpenAI",
            OpenAIConfigError,
        )
    return OpenAI(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="YAML settings file")
    parser.add_argument("--env-file", type=Path, help="Optional dotenv file, usually .env")
    parser.add_argument("--dry-run", action="store_true", help="Redact without calling OpenAI")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Prompt text; the default is synthetic")
    prompt_group.add_argument("--prompt-file", type=Path, help="Read prompt text from a file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        prompt = prompt_from_args(args.prompt, args.prompt_file, OpenAIConfigError)
        settings = load_settings(
            config_path=args.config,
            env_file=args.env_file,
            require_openai=not args.dry_run,
        )
        result = (
            redact_for_openai(prompt, settings)
            if args.dry_run
            else ask_openai(prompt, settings)
        )
    except OpenAIConfigError as exc:
        print("configuration error: " + str(exc), file=sys.stderr)
        return 2
    except OpenAICallError as exc:
        print("openai error: " + str(exc), file=sys.stderr)
        return 3

    print("mode: " + ("dry-run" if args.dry_run else "live"))
    print("model: " + (settings.model or "not configured"))
    print("sent-to-openai: " + result.redacted_input)
    print("findings: " + format_counts(result.finding_counts))
    if result.output_text is None:
        print("openai-response: skipped (--dry-run)")
    else:
        print("openai-response: " + result.output_text)
        print(
            "metrics: "
            + format_metrics(result.input_tokens, result.output_tokens, result.total_tokens)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
