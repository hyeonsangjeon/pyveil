# pyveil

<p align="center">
  <a href="https://pypi.org/project/pyveil/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pyveil?style=flat-square"></a>
  <a href="https://www.python.org/"><img alt="Python 3.8 to 3.14" src="https://img.shields.io/badge/python-3.8%20to%203.14-3776AB?style=flat-square"></a>
  <a href="https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml"><img alt="Tested on Python 3.8 to 3.14" src="https://img.shields.io/badge/tested-Python%203.8%20to%203.14-brightgreen?style=flat-square"></a>
  <a href="https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml/badge.svg"></a>
  <a href="#development"><img alt="Coverage 91 percent" src="https://img.shields.io/badge/coverage-91%25-brightgreen?style=flat-square"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green?style=flat-square"></a>
  <img alt="Core dependencies: zero" src="https://img.shields.io/badge/core%20deps-zero-111827?style=flat-square">
  <img alt="Typed package" src="https://img.shields.io/badge/typed-py.typed-7C3AED?style=flat-square">
  <img alt="Agent-native redaction" src="https://img.shields.io/badge/agent--native-redaction-FF6B35?style=flat-square">
</p>

Redact secrets before your AI agent sees them.

`pyveil` is agent-native redaction middleware for prompts, tool calls, MCP resources, logs, traces, and memory. Put it before sensitive context reaches a model, tool, memory store, trace exporter, or log sink.

<p align="center">
  <img src="https://raw.githubusercontent.com/hyeonsangjeon/pyveil/main/docs/media/pyveil-awesome-demo.gif"
       alt="pyveil redacts synthetic sensitive context before it crosses agent trust boundaries"
       width="820">
</p>

```text
user data / tool data / resource data
        -> pyveil
        -> agent prompt / tool call / MCP resource / memory / trace / log
```

`pyveil` is intentionally small: standard-library core, deterministic HMAC placeholders, channel-aware policy, and high-precision detectors for v0.1.

## Install

```bash
pip install pyveil
```

[PyPI package](https://pypi.org/project/pyveil/)

Python `3.8` through `3.14` are tested.

## 30 Second Quickstart

```python
from pyveil import Veil

veil = Veil.high(secret=b"tenant-or-run-secret", scope="tenant/session")

result = veil.redact_text(
    "Email alice@example.com and call 010-1234-5678",
    channel="prompt.input",
)

print(result.text)
# Email [EMAIL:...] and call [PHONE:...]
```

For one-off scripts:

```python
from pyveil import redact_text

safe = redact_text(
    "email alice@example.com",
    secret=b"tenant-or-run-secret",
    scope="tenant/session",
)
print(safe.text)
```

## Usage Guides

Short no-audio walkthroughs are attached to the `v0.1.1` GitHub release:

- [English usage guide](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.1/pyveil-usage-guide-en.mp4)
- [Korean usage guide](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.1/pyveil-usage-guide-ko.mp4)

## Why Middleware

Prompt-only redaction asks the model to handle sensitive data after the model has already seen it. `pyveil` redacts before context crosses an agent boundary.

Classic PII masking libraries usually treat redaction as "text in, text out." Agents leak through more surfaces:

| Channel | Typical use |
| --- | --- |
| `prompt.input` | User or retrieved context before model input |
| `prompt.output` | Model output before display or chaining |
| `tool.call.arguments` | Arguments before a model-controlled tool runs |
| `tool.call.result` | Tool results before returning to the model |
| `mcp.resource.content` | MCP resource content before agent use |
| `memory.write` | Memory text before embedding or persistence |
| `trace.span.attributes` | Observability attributes before export |
| `log.record` | Application logs before handlers or sinks |

Channels are first-class so policy can decide whether a finding should be redacted, passed, or blocked.

## Text Redaction

```python
from pyveil import Channel, Veil

veil = Veil.high(
    secret=b"tenant-secret",
    scope="tenant_123/session_456",
    max_input_chars=1_000_000,
)

safe = veil.redact_text(
    "Authorization: Bearer synthetic-token-value",
    channel=Channel.PROMPT_INPUT,
)

print(safe.text)
print(safe.findings[0].type)
```

`Finding` objects do not contain raw sensitive values by default. They include metadata such as `type`, `detector`, `rule_id`, `path`, `placeholder`, and `fingerprint`.

## Structured Redaction

Use `redact_data` for dictionaries, lists, JSON strings, tool arguments, MCP-like payloads, trace attributes, and memory records.

```python
from pyveil import Veil

payload = {
    "user": "alice@example.com",
    "headers": {"Authorization": "Bearer synthetic-token-value"},
    "args": {"phone": "+82 10-1234-5678"},
    "debug": True,
}

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session")
safe = veil.redact_data(payload, channel="tool.call.result")

print(safe.data)
```

Structured payloads keep their shape. Non-string scalar values under sensitive key names, such as `{"api_key": 12345}` or `{"password": True}`, preserve their original type instead of being replaced with strings.

## HIGH vs LOW

Use `HIGH` by default for agents and external boundaries.

| Level | Intended use | Example |
| --- | --- | --- |
| `HIGH` | Agent, model, tool, MCP, memory, trace, and log boundaries | `alice@example.com -> [EMAIL:a13f7c91b0d2]` |
| `LOW` | Human-facing diagnostics or legacy-style previews | `alice@example.com -> al***@e******.com` |

Credential-like values remain aggressively hidden. There is no reversible vault or unmasking API in v0.1.

## Policy

The default policy redacts supported findings and blocks credential-like material in `tool.call.arguments`.

```python
from pyveil import Action, Channel, Entity, Policy, Veil

policy = Policy.default_high().override(
    Channel.PROMPT_INPUT,
    Entity.EMAIL,
    Action.PASS,
)

veil = Veil.high(secret=b"tenant-secret", policy=policy)
```

When both `policy` and `level` are supplied, the explicit `policy` decides channel levels and actions. Build one `Veil` per tenant, session, or run and reuse it in tight loops.

## CLI

```bash
pyveil init
export PYVEIL_SECRET="tenant-or-run-secret"
export PYVEIL_SCOPE="tenant/session"

pyveil redact prompt.txt --channel prompt.input --level high
pyveil redact request.json --channel tool.call.result --format json
pyveil scan prompt.txt --format json
pyveil test-config pyveil.yaml
```

JSON-shaped input is treated as structured data. Use `--format json` for `pyveil redact` when the input is JSON.

## Detectors

v0.1 focuses on high-precision, low-dependency detection:

- Email addresses
- Korean and international-ish phone numbers
- Credit card numbers with Luhn validation
- JWTs
- Bearer and Basic authorization headers
- Private key blocks
- Common API key and provider token prefixes
- URL query secrets such as `access_token=`
- Key-value secrets in text and structured payloads

Broad name and address detection is intentionally out of scope for core v0.1 unless supplied as known values or custom rules in a future release.

## Safety Model

`pyveil` aims to reduce sensitive-context exposure at agent boundaries.

- No raw sensitive value is stored in `Finding` by default.
- Stable placeholders use HMAC-SHA256 with caller-provided secrets.
- `scope` separates placeholders across tenants, sessions, or runs.
- `max_input_chars` limits input size before detection.
- Core v0.1 has no network calls and no required third-party runtime dependencies.

Use it with access control, logging discipline, secret scanning, provider-side controls, and normal application security review.

## Non-goals

`pyveil` is not:

- A Presidio clone
- An enterprise DLP system
- A compliance guarantee
- A secret-scanning replacement
- A prompt-injection firewall
- A reversible token vault

## Agent Adoption

This repository includes files meant for coding agents and LLM readers:

- [AGENTS.md](AGENTS.md) for agent instructions
- [llms.txt](llms.txt) for LLM-friendly navigation
- [docs/threat-model.md](docs/threat-model.md)
- [docs/known-limitations.md](docs/known-limitations.md)
- [docs/detector-provenance.md](docs/detector-provenance.md)
- [docs/release-checklist.md](docs/release-checklist.md)
- [docs/integrations/mcp.md](docs/integrations/mcp.md)
- [docs/integrations/logging.md](docs/integrations/logging.md)
- [docs/integrations/tracing.md](docs/integrations/tracing.md)

Examples:

- [examples/basic_usage.py](examples/basic_usage.py)
- [examples/redact_json.py](examples/redact_json.py)
- [examples/log_filter.py](examples/log_filter.py)
- [examples/mcp_tool_result.py](examples/mcp_tool_result.py)
- [examples/memory_write.py](examples/memory_write.py)

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
```

Full local release check:

```bash
for v in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-venv-$v" uv run --python "$v" --extra test pytest -q --disable-warnings --no-cov
done

uv run --extra dev python -m build
uv run --extra dev python -m twine check dist/*
```
