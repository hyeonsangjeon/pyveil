# Anthropic / Claude Integration

Use `pyveil.integrations.anthropic` to redact a prompt immediately before the
official Anthropic Python SDK serializes a Claude Messages API request.

```text
raw prompt -> pyveil HIGH redaction -> Anthropic client.messages.create -> Claude
```

## Verification Status

This repository has no Anthropic API key and does not claim a live paid
request. The integration is verified with:

- fake-client unit tests that capture the exact `messages.create(...)` arguments;
- the official `anthropic` package connected to a local `httpx.MockTransport`;
- assertions against the real SDK's serialized `/v1/messages` JSON body;
- keyless CLI dry-runs, package builds, and installed-wheel smokes.

The mock transport never opens a network connection and cannot consume Claude
usage credits.

## Install

```bash
pip install "pyveil[anthropic]"
```

The pyveil core remains Python 3.8+. The current official Anthropic SDK
requires Python 3.9+, so live Claude integration and SDK contract tests use
Python 3.9 through 3.14. Keyless dry-run remains available on Python 3.8.

## Dry Run Without An API Key

```bash
PYVEIL_SECRET=docs-demo-secret \
ANTHROPIC_MODEL=claude-haiku-4-5 \
  python -m pyveil.integrations.anthropic --dry-run
```

```text
mode: dry-run
model: claude-haiku-4-5
sent-to-anthropic: Write a one-sentence support follow-up for [EMAIL:0b77abd1b26b] or [PHONE:ec56e2456ba2].
findings: EMAIL=1, PHONE=1
anthropic-response: skipped (--dry-run)
```

## Live Call

When an API account has usage credits, configure the key and an accessible
model:

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_MODEL="claude-haiku-4-5"
export PYVEIL_SECRET="a-long-random-hmac-secret"
python -m pyveil.integrations.anthropic
```

Or call the reusable API:

```python
from pyveil.integrations.anthropic import ask_anthropic, load_settings

settings = load_settings()
result = ask_anthropic(
    "Write a support reply for alice@example.com or 010-1234-5678.",
    settings,
)

print(result.redacted_input)  # exact Messages API user content
print(result.output_text)
print(result.input_tokens, result.output_tokens)
```

The helper uses the official Messages API shape:

```python
message = client.messages.create(
    model=settings.model,
    max_tokens=settings.max_tokens,
    messages=[{"role": "user", "content": safe.redacted_input}],
)
```

Anthropic documents this interface in its
[official Python SDK guide](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python).
Model IDs and aliases are account- and lifecycle-dependent, so
`ANTHROPIC_MODEL` remains configurable.

## Configuration

Priority is process environment, `.env`, YAML, then defaults.

| Environment | YAML key | Default | Purpose |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | `anthropic.api_key_env` | required live | Name/value source for provider auth |
| `ANTHROPIC_MODEL` | `anthropic.model` | required live | Claude model ID or alias |
| `ANTHROPIC_BASE_URL` | `anthropic.base_url` | official SDK default | Optional custom endpoint |
| `ANTHROPIC_MAX_TOKENS` | `anthropic.max_tokens` | `256` | Maximum generated tokens |
| `ANTHROPIC_TIMEOUT` | `anthropic.timeout_seconds` | `120` | SDK timeout in seconds |
| `PYVEIL_SECRET` | `pyveil.secret_env` | required | HMAC secret environment variable |
| `PYVEIL_SCOPE` | `pyveil.scope` | `anthropic/example` | Placeholder namespace |

```bash
python -m pyveil.integrations.anthropic \
  --config examples/anthropic.example.yaml \
  --env-file .env
```

YAML may name the environment variables that hold secrets, but direct
`anthropic.api_key` and `pyveil.secret` fields are rejected.

## Run The Offline SDK Contract

```bash
pip install -e ".[anthropic,test]"
pytest tests/test_provider_contracts.py -m provider_contract --no-cov
```

The test verifies that the official SDK receives placeholders and that the raw
synthetic email and phone never appear in its serialized request body.

## Boundary Notes

- Anthropic uses a top-level `system` parameter rather than a `system` message
  role. This v0 template protects one user prompt and intentionally keeps the
  provider call small.
- A custom `ANTHROPIC_BASE_URL` is another trust boundary. pyveil validates the
  URL and rejects embedded credentials, but it cannot evaluate the operator.
- Provider output may contain new sensitive values. Redact it again with
  channel `prompt.output` before logging, persistence, or downstream chaining.
- Older Claude models are not free and may be retired. Configure a currently
  available model instead of relying on a historical ID.
- Regex and known-value rules do not discover arbitrary names or addresses.
