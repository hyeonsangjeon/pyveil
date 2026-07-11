"""Command line interface for pyveil."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple

from . import __version__
from .core import Veil
from .exceptions import BlockedSensitiveData
from .findings import RedactionResult
from .levels import Level
from .utils import looks_like_json

DEFAULT_CONFIG = """# pyveil.yaml
# Reference schema for review and validation.
# pyveil 0.2.x CLI commands use flags and PYVEIL_* environment variables;
# they do not automatically load this file.
version: 1
default_level: HIGH
placeholder:
  digest: hmac-sha256
  length: 12
  scope: tenant_session
channels:
  prompt.input:
    level: HIGH
  tool.call.arguments:
    level: HIGH
    block:
      - AUTH_HEADER
      - PRIVATE_KEY
      - API_KEY
      - JWT
      - KV_SECRET
      - URL_QUERY_SECRET
detectors:
  email: true
  phone: true
  credit_card: true
  jwt: true
  auth_header: true
  private_key: true
  api_key: true
  url_query_secret: true
  kv_secret: true
  names: false
  addresses: false
safety:
  include_raw_findings: false
  max_input_chars: 1000000
"""


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pyveil")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    redact = subcommands.add_parser("redact", help="Redact text from a file or stdin")
    redact.add_argument("path", nargs="?", help="Input file. Use '-' or omit for stdin.")
    redact.add_argument("--channel", default="prompt.input")
    redact.add_argument("--level", choices=["low", "high"], default="high")
    redact.add_argument("--secret", help="HMAC secret. Defaults to PYVEIL_SECRET.")
    redact.add_argument("--format", choices=["text", "json"], default="text")
    redact.add_argument(
        "--scope", default=None, help="Placeholder scope. Defaults to PYVEIL_SCOPE or 'default'."
    )

    scan = subcommands.add_parser("scan", help="Scan text and emit findings as JSON")
    scan.add_argument("path", nargs="?", help="Input file. Use '-' or omit for stdin.")
    scan.add_argument("--channel", default="prompt.input")
    scan.add_argument("--secret", help="HMAC secret. Defaults to PYVEIL_SECRET.")
    scan.add_argument("--format", choices=["json"], default="json")
    scan.add_argument(
        "--scope", default=None, help="Placeholder scope. Defaults to PYVEIL_SCOPE or 'default'."
    )

    init = subcommands.add_parser("init", help="Write a reference pyveil.yaml schema")
    init.add_argument("path", nargs="?", default="pyveil.yaml")

    test_config = subcommands.add_parser("test-config", help="Validate a reference pyveil.yaml shape")
    test_config.add_argument("path", nargs="?", default="pyveil.yaml")

    demo = subcommands.add_parser("demo", help="Run a synthetic before/after redaction demo")
    demo.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "init":
        Path(args.path).write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(args.path)
        return 0
    if args.command == "test-config":
        return _test_config(args.path)
    if args.command == "demo":
        return _demo(args.format)

    text = _read_text(args.path)
    secret = _resolve_cli_secret(args.secret)
    if secret is None:
        print("secret is required; pass --secret or set PYVEIL_SECRET", file=sys.stderr)
        return 2
    scope = _resolve_cli_scope(args.scope)
    veil = Veil(
        secret=secret,
        level=Level.HIGH if getattr(args, "level", "high") == "high" else Level.LOW,
        scope=scope,
    )
    try:
        result, structured = _redact_input(veil, text, channel=args.channel)
    except BlockedSensitiveData as exc:
        print(exc.summary(), file=sys.stderr)
        return 2

    if args.command == "scan":
        print(_findings_json(result))
        return 0
    if structured and args.format == "text":
        print("structured JSON input requires --format json", file=sys.stderr)
        return 2
    if args.format == "json":
        print(_result_json(result))
    else:
        output = _text_output(result, structured=structured)
        print(output, end="" if output.endswith("\n") else "\n")
    return 0


def _read_text(path: Optional[str]) -> str:
    if path and path != "-":
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _resolve_cli_secret(secret: Optional[str]) -> Optional[str]:
    return secret or os.environ.get("PYVEIL_SECRET")


def _resolve_cli_scope(scope: Optional[str]) -> str:
    return scope or os.environ.get("PYVEIL_SCOPE") or "default"


def _redact_input(veil: Veil, text: str, channel: str) -> Tuple[RedactionResult, bool]:
    if looks_like_json(text):
        try:
            return veil.redact_data(json.loads(text), channel=channel), True
        except json.JSONDecodeError:
            pass
    return veil.redact_text(text, channel=channel), False


def _text_output(result: RedactionResult, structured: bool) -> str:
    if structured:
        return json.dumps(result.data, ensure_ascii=False, separators=(",", ":"))
    return result.text


def _findings_json(result: RedactionResult) -> str:
    payload = {
        "findings": [
            {
                "type": finding.type,
                "detector": finding.detector,
                "rule_id": finding.rule_id,
                "start": finding.start,
                "end": finding.end,
                "path": finding.path,
                "placeholder": finding.placeholder,
                "fingerprint": finding.fingerprint,
            }
            for finding in result.findings
        ],
        "stats": {
            "total_findings": result.stats.total_findings,
            "counts_by_type": result.stats.counts_by_type,
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _result_json(result: RedactionResult) -> str:
    payload = {
        "data": result.data,
        "stats": {
            "total_findings": result.stats.total_findings,
            "counts_by_type": result.stats.counts_by_type,
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _test_config(path: str) -> int:
    config_path = Path(path)
    if not config_path.exists():
        print(f"{path} does not exist", file=sys.stderr)
        return 1
    text = config_path.read_text(encoding="utf-8")
    required = ("version:", "default_level:", "channels:", "detectors:", "safety:")
    missing = [item for item in required if item not in text]
    if missing:
        print(f"missing required sections: {', '.join(missing)}", file=sys.stderr)
        return 1
    print("ok")
    return 0


def _demo(output_format: str) -> int:
    text = (
        "Email alice@example.com, call 010-1234-5678, and use API key "
        "sk-proj-DEMO_ONLY_000000000000000000."
    )
    veil = Veil.high(secret=b"pyveil-demo-only", scope="synthetic-demo")
    result = veil.redact_text(text, channel="prompt.input")
    if output_format == "json":
        payload = {
            "before": text,
            "after": result.text,
            "counts_by_type": result.stats.counts_by_type,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("before: " + text)
        print("after:  " + result.text)
        print("found:  " + ", ".join(sorted(result.stats.counts_by_type)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
