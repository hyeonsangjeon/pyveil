"""Strict, dependency-free configuration for reproducible file redaction."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from .constants import Channel, Entity
from .levels import Action, Level
from .policy import Policy

CONFIG_NAME = "pyveil.json"
CONFIG_LIMIT = 65_536
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "pyveil_version",
        "input",
        "input_format",
        "input_origin",
        "output_dir",
        "scope",
        "channel",
        "level",
        "max_input_chars",
        "actions",
    }
)


class RunConfigError(ValueError):
    """An invalid run configuration; messages never echo field values."""


class StrictJSONError(ValueError):
    """Ambiguous or non-finite JSON, without echoing input."""


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError("duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise StrictJSONError("non-finite JSON numbers are not allowed")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise StrictJSONError("non-finite JSON numbers are not allowed")
    return number


def parse_json(text: str) -> Any:
    """Parse JSON without accepting duplicate keys, NaN, or Infinity."""

    return json.loads(
        text,
        object_pairs_hook=_object_pairs,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RunConfigError(label + " must be a non-empty string without NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise RunConfigError(label + " must contain valid Unicode") from exc
    return value


@dataclass(frozen=True)
class RunConfig:
    """Resolved paths and settings; environment affects only the named secret."""

    path: Path = field(repr=False)
    sha256: str
    input_path: Path = field(repr=False)
    output_dir: Path = field(repr=False)
    input_format: str
    input_origin: str
    scope: str = field(repr=False)
    channel: Channel
    level: Level
    max_input_chars: int
    actions: tuple[tuple[Entity, Action], ...]
    secret_env: str | None
    secret_file: Path | None = field(repr=False)

    def policy(self) -> Policy:
        policy = Policy(default_level=self.level)
        for entity, action in self.actions:
            policy = policy.override(self.channel, entity, action)
        return policy


def load_run_config(path: Path) -> RunConfig:
    """Validate the entire ledger before reading an input or creating outputs."""

    if path.suffix.lower() != ".json":
        raise RunConfigError(
            "run configuration must be JSON; legacy pyveil.yaml is not executable. "
            "Create pyveil.json with 'pyveil init --input FILE'"
        )
    try:
        if not path.is_file():
            raise RunConfigError("run config is not a regular file; use 'pyveil init'")
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read(CONFIG_LIMIT + 1)
    except (OSError, UnicodeError) as exc:
        raise RunConfigError("cannot read run config as UTF-8") from exc
    if len(text) > CONFIG_LIMIT:
        raise RunConfigError("run config exceeds 65536 characters")
    try:
        data = parse_json(text)
    except (ValueError, RecursionError) as exc:
        raise RunConfigError(
            "run config must be valid JSON with unique keys and finite numbers"
        ) from exc
    if not isinstance(data, dict):
        raise RunConfigError("run config must be a JSON object")
    if set(data) - REQUIRED_FIELDS - {"secret_env", "secret_file"}:
        raise RunConfigError("unknown run config field; compare with 'pyveil init' output")
    missing = REQUIRED_FIELDS - set(data)
    if missing:
        raise RunConfigError("missing run config fields: " + ", ".join(sorted(missing)))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise RunConfigError("schema_version must be 1")
    if data["pyveil_version"] != __version__:
        raise RunConfigError(
            "pyveil_version does not match the installed package; install the pinned version "
            "or deliberately update the config after reviewing the changelog"
        )
    if data["input_format"] not in ("text", "json"):
        raise RunConfigError("input_format must be text or json")
    if data["input_origin"] not in ("user-provided", "synthetic"):
        raise RunConfigError("input_origin must be user-provided or synthetic")
    if type(data["max_input_chars"]) is not int or not 1 <= data["max_input_chars"] <= 1_000_000:
        raise RunConfigError("max_input_chars must be an integer between 1 and 1000000")
    try:
        channel = Channel(data["channel"])
        level = Level(data["level"])
    except (ValueError, TypeError) as exc:
        raise RunConfigError("channel or level is not a supported value") from exc
    actions = data["actions"]
    if not isinstance(actions, dict):
        raise RunConfigError("actions must be an object mapping entity names to actions")
    try:
        overrides = tuple((Entity(key), Action(value)) for key, value in sorted(actions.items()))
    except (ValueError, TypeError) as exc:
        raise RunConfigError(
            "actions must use supported entity names and REDACT, PASS, or BLOCK"
        ) from exc
    if ("secret_env" in data) == ("secret_file" in data):
        raise RunConfigError("configure exactly one of secret_env or secret_file")
    secret_env = None
    secret_file = None
    parent = path.resolve().parent
    if "secret_env" in data:
        secret_env = _text(data["secret_env"], "secret_env")
        if ENV_NAME_RE.fullmatch(secret_env) is None:
            raise RunConfigError("secret_env must be an environment variable name, not its value")
    else:
        secret_file = parent / _text(data["secret_file"], "secret_file")
    input_path = parent / _text(data["input"], "input")
    output_dir = parent / _text(data["output_dir"], "output_dir")
    try:
        reserved = {path.resolve()}
        if secret_file is not None:
            if secret_file.resolve() in reserved or (
                secret_file.is_file() and secret_file.samefile(path)
            ):
                raise RunConfigError("secret_file must not be the config file")
            reserved.add(secret_file.resolve())
        if input_path.resolve() in reserved or (
            input_path.is_file()
            and any(target.is_file() and input_path.samefile(target) for target in reserved)
        ):
            raise RunConfigError("input must not be the config or secret file")
    except (OSError, RuntimeError) as exc:
        raise RunConfigError("cannot resolve run paths; check file links and permissions") from exc
    return RunConfig(
        path=path.resolve(),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        input_path=input_path,
        output_dir=output_dir,
        input_format=data["input_format"],
        input_origin=data["input_origin"],
        scope=_text(data["scope"], "scope"),
        channel=channel,
        level=level,
        max_input_chars=data["max_input_chars"],
        actions=overrides,
        secret_env=secret_env,
        secret_file=secret_file,
    )
