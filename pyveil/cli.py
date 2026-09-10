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
from .file_run import FileRunError, init_run_config, run_file
from .findings import RedactionResult
from .levels import Level
from .run_config import CONFIG_NAME, RunConfigError, load_run_config
from .utils import looks_like_json


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

    init = subcommands.add_parser("init", help="Create an executable pyveil.json without overwriting files")
    init.add_argument("path", nargs="?", default=CONFIG_NAME)
    source = init.add_mutually_exclusive_group()
    source.add_argument("--input", help="Input file, relative to the config directory")
    source.add_argument("--example", action="store_true", help="Create a labeled synthetic input file")
    init.add_argument("--input-format", choices=["text", "json"], help="Default: json for .json, text otherwise")
    init.add_argument("--secret-env", help="Use this environment variable instead of creating a private local key")

    test_config = subcommands.add_parser("test-config", help="Strictly validate pyveil.json; do not run")
    test_config.add_argument("path", nargs="?", default=CONFIG_NAME)

    run = subcommands.add_parser("run", help="Redact the configured input file and persist output plus receipt")
    run.add_argument("path", nargs="?", default=CONFIG_NAME)
    run.add_argument("--format", choices=["text", "json"], default="text", help="Format of output locations, not the redacted payload")

    demo = subcommands.add_parser("demo", help="Run a synthetic before/after redaction demo")
    demo.add_argument("--format", choices=["text", "json"], default="text")

    replay = subcommands.add_parser(
        "replay",
        help="Verify six agent privacy boundaries with synthetic offline cases",
    )
    replay.add_argument("--format", choices=["json", "markdown"], default="json")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command in {"init", "test-config", "run"}:
        return _configured_command(args)
    if args.command == "demo":
        return _demo(args.format)
    if args.command == "replay":
        return _privacy_replay(args.format)

    secret = _resolve_cli_secret(args.secret)
    if secret is None:
        print("secret is required; pass --secret or set PYVEIL_SECRET", file=sys.stderr)
        return 2
    scope = _resolve_cli_scope(args.scope)
    try:
        text = _read_text(args.path)
        veil = Veil(
            secret=secret,
            level=Level.HIGH if getattr(args, "level", "high") == "high" else Level.LOW,
            scope=scope,
        )
        result, structured = _redact_input(veil, text, channel=args.channel)
    except BlockedSensitiveData as exc:
        print(exc.summary(), file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print("cannot read input as UTF-8; check the file and permissions", file=sys.stderr)
        return 1
    except (ValueError, RecursionError):
        print("redaction failed; check input size, nesting, and secret settings", file=sys.stderr)
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


def _configured_command(args: argparse.Namespace) -> int:
    try:
        path = Path(args.path)
        if args.command == "init":
            init_run_config(
                path,
                input_path=args.input,
                input_format=args.input_format,
                example=args.example,
                secret_env=args.secret_env,
            )
            print("Created " + str(path) + "; keep the private key out of version control.")
            print("Run: pyveil run " + str(path))
        elif args.command == "test-config":
            load_run_config(path)
            print("ok: executable JSON config; input and secret are checked by 'pyveil run'")
        else:
            completed = run_file(path)
            locations = {"status": "completed", "output": str(completed.output), "receipt": str(completed.receipt)}
            if args.format == "json":
                print(json.dumps(locations, sort_keys=True))
            else:
                print("Output: " + locations["output"])
                print("Receipt: " + locations["receipt"])
                print("Local redaction completed; no provider was called.")
    except BlockedSensitiveData as exc:
        print(exc.summary(), file=sys.stderr)
        return 2
    except RunConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileRunError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError:
        print("filesystem operation failed; check permissions and remove incomplete run files", file=sys.stderr)
        return 1
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


def _privacy_replay(output_format: str) -> int:
    from .privacy_replay import replay_output

    rendered, exit_code = replay_output(output_format)
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
