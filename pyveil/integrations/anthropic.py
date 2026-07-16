"""Redact a prompt before sending it to the Claude Messages API.

Install the optional integration dependencies:

    pip install "pyveil[anthropic]"

Prove the boundary without an API key or network request:

    PYVEIL_SECRET=local-demo-secret \
      python -m pyveil.integrations.anthropic --dry-run

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
    "AnthropicCallError",
    "AnthropicCallResult",
    "AnthropicConfigError",
    "AnthropicSettings",
    "ask_anthropic",
    "load_settings",
    "redact_for_anthropic",
]

DEFAULT_SCOPE = "anthropic/example"


class AnthropicConfigError(ValueError):
    """Raised when the Anthropic integration configuration is invalid."""


class AnthropicCallError(RuntimeError):
    """Raised when a safe Anthropic request cannot be completed."""


@dataclass(frozen=True)
class AnthropicSettings:
    """Runtime settings resolved from environment variables and YAML."""

    pyveil_secret: str = field(repr=False)
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    base_url: str | None = None
    pyveil_scope: str = DEFAULT_SCOPE
    max_tokens: int = 256
    timeout_seconds: float = 120.0

    def validate(self) -> None:
        validate_remote_settings(
            provider_name="Anthropic",
            model=self.model,
            base_url=self.base_url,
            pyveil_secret=self.pyveil_secret,
            max_tokens=self.max_tokens,
            max_tokens_name="max_tokens",
            timeout_seconds=self.timeout_seconds,
            error_type=AnthropicConfigError,
        )

    def validate_live(self) -> None:
        self.validate()
        missing = []
        if not self.model:
            missing.append("ANTHROPIC_MODEL")
        if not self.api_key:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            raise AnthropicConfigError(
                "missing live Anthropic settings: " + ", ".join(missing)
            )


@dataclass(frozen=True)
class AnthropicCallResult:
    """Safe request details, provider response, and optional usage metrics."""

    redacted_input: str
    finding_counts: Mapping[str, int]
    output_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


def load_settings(
    config_path: Path | None = None,
    env_file: Path | None = None,
    require_anthropic: bool = True,
) -> AnthropicSettings:
    """Load process environment, optional dotenv, and non-secret YAML settings."""

    values = load_remote_settings(
        provider_section="anthropic",
        env_prefix="ANTHROPIC",
        max_tokens_env="ANTHROPIC_MAX_TOKENS",
        max_tokens_key="max_tokens",
        default_scope=DEFAULT_SCOPE,
        extra_name="anthropic",
        error_type=AnthropicConfigError,
        config_path=config_path,
        env_file=env_file,
    )
    settings = AnthropicSettings(
        pyveil_secret=values.pyveil_secret,
        api_key=values.api_key,
        model=values.model,
        base_url=values.base_url,
        pyveil_scope=values.pyveil_scope,
        max_tokens=values.max_tokens,
        timeout_seconds=values.timeout_seconds,
    )
    if require_anthropic:
        settings.validate_live()
    else:
        settings.validate()
    return settings


def redact_for_anthropic(prompt: str, settings: AnthropicSettings) -> AnthropicCallResult:
    """Return exactly what may cross the Anthropic SDK boundary."""

    settings.validate()
    text, counts = redact_prompt(prompt, settings.pyveil_secret, settings.pyveil_scope)
    return AnthropicCallResult(redacted_input=text, finding_counts=counts)


def ask_anthropic(
    prompt: str,
    settings: AnthropicSettings,
    client: Any | None = None,
) -> AnthropicCallResult:
    """Redact ``prompt``, call the Messages API, and return safe metadata."""

    settings.validate_live()
    safe = redact_for_anthropic(prompt, settings)
    anthropic_client = client if client is not None else _build_client(settings)
    try:
        response = anthropic_client.messages.create(
            model=settings.model,
            max_tokens=settings.max_tokens,
            messages=[{"role": "user", "content": safe.redacted_input}],
        )
    except Exception as exc:
        raise AnthropicCallError(
            "Anthropic request failed; verify credentials, model access, and network connectivity"
        ) from exc

    output_text = _text_content(response)
    if not output_text:
        raise AnthropicCallError("Anthropic response did not include text content")

    usage = response_value(response, "usage")
    return AnthropicCallResult(
        redacted_input=safe.redacted_input,
        finding_counts=safe.finding_counts,
        output_text=output_text,
        input_tokens=optional_int(usage, "input_tokens"),
        output_tokens=optional_int(usage, "output_tokens"),
        request_id=optional_string(response, "_request_id"),
    )


def _text_content(response: Any) -> str | None:
    content = response_value(response, "content")
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
        return None
    parts = []
    for block in content:
        if response_value(block, "type") != "text":
            continue
        text = response_value(block, "text")
        if isinstance(text, str):
            parts.append(text)
    combined = "".join(parts)
    return combined if combined.strip() else None


def _build_client(settings: AnthropicSettings) -> Any:
    if sys.version_info < (3, 9):  # pragma: no cover - integration SDK boundary
        raise AnthropicConfigError("the official Anthropic Python SDK requires Python 3.9+")
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise AnthropicConfigError(
            'install the Anthropic integration dependencies: pip install "pyveil[anthropic]"'
        ) from exc

    kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_seconds,
    }
    if settings.base_url:
        kwargs["base_url"] = normalize_base_url(
            settings.base_url,
            "Anthropic",
            AnthropicConfigError,
        )
    return Anthropic(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="YAML settings file")
    parser.add_argument("--env-file", type=Path, help="Optional dotenv file, usually .env")
    parser.add_argument("--dry-run", action="store_true", help="Redact without calling Anthropic")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Prompt text; the default is synthetic")
    prompt_group.add_argument("--prompt-file", type=Path, help="Read prompt text from a file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        prompt = prompt_from_args(args.prompt, args.prompt_file, AnthropicConfigError)
        settings = load_settings(
            config_path=args.config,
            env_file=args.env_file,
            require_anthropic=not args.dry_run,
        )
        result = (
            redact_for_anthropic(prompt, settings)
            if args.dry_run
            else ask_anthropic(prompt, settings)
        )
    except AnthropicConfigError as exc:
        print("configuration error: " + str(exc), file=sys.stderr)
        return 2
    except AnthropicCallError as exc:
        print("anthropic error: " + str(exc), file=sys.stderr)
        return 3

    print("mode: " + ("dry-run" if args.dry_run else "live"))
    print("model: " + (settings.model or "not configured"))
    print("sent-to-anthropic: " + result.redacted_input)
    print("findings: " + format_counts(result.finding_counts))
    if result.output_text is None:
        print("anthropic-response: skipped (--dry-run)")
    else:
        print("anthropic-response: " + result.output_text)
        print("metrics: " + format_metrics(result.input_tokens, result.output_tokens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
