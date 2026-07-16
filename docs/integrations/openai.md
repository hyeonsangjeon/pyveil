# OpenAI Integration

Use `pyveil.integrations.openai` to redact a prompt immediately before the
official OpenAI Python SDK serializes a Responses API request.

```text
raw prompt -> pyveil HIGH redaction -> OpenAI client.responses.create -> model
```

## Verification Status

This repository has no OpenAI API key and does not claim a live paid request.
The integration is verified with:

- fake-client unit tests that capture the exact `responses.create(...)` arguments;
- the official `openai` package connected to a local `httpx.MockTransport`;
- assertions against the real SDK's serialized `/v1/responses` JSON body;
- keyless CLI dry-runs, package builds, and installed-wheel smokes.

The mock transport never opens a network connection and cannot incur API cost.

## Install

```bash
pip install "pyveil[openai]"
```

The pyveil core remains Python 3.8+. The current official OpenAI SDK requires
Python 3.9+, so live OpenAI integration and SDK contract tests use Python
3.9 through 3.14. Keyless dry-run remains available on Python 3.8.

## Dry Run Without An API Key

Set only the local HMAC secret. A model is optional for dry-run, but setting it
makes the inspected payload match the intended live configuration:

```bash
PYVEIL_SECRET=docs-demo-secret \
OPENAI_MODEL=gpt-5.6-luna \
  python -m pyveil.integrations.openai --dry-run
```

```text
mode: dry-run
model: gpt-5.6-luna
sent-to-openai: Write a one-sentence support follow-up for [EMAIL:17c25f8a4fe3] or [PHONE:3f6dc5a3c9f3].
findings: EMAIL=1, PHONE=1
openai-response: skipped (--dry-run)
```

## Live Call

When an API account is available, configure the key and an accessible model:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-luna"
export PYVEIL_SECRET="a-long-random-hmac-secret"
python -m pyveil.integrations.openai
```

Or call the reusable API:

```python
from pyveil.integrations.openai import ask_openai, load_settings

settings = load_settings()
result = ask_openai(
    "Write a support reply for alice@example.com or 010-1234-5678.",
    settings,
)

print(result.redacted_input)  # exact Responses API input
print(result.output_text)
print(result.input_tokens, result.output_tokens, result.total_tokens)
```

The helper uses the official Responses API shape:

```python
response = client.responses.create(
    model=settings.model,
    input=safe.redacted_input,
    max_output_tokens=settings.max_output_tokens,
)
```

OpenAI documents the Responses API as the primary API in its
[official Python SDK](https://github.com/openai/openai-python). Model access and
availability are account-specific; `OPENAI_MODEL` is configurable rather than
embedded in pyveil's runtime code.

## Configuration

Priority is process environment, `.env`, YAML, then defaults.

| Environment | YAML key | Default | Purpose |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | `openai.api_key_env` | required live | Name/value source for provider auth |
| `OPENAI_MODEL` | `openai.model` | required live | Responses API model |
| `OPENAI_BASE_URL` | `openai.base_url` | official SDK default | Optional compatible endpoint |
| `OPENAI_MAX_OUTPUT_TOKENS` | `openai.max_output_tokens` | `256` | Maximum generated tokens |
| `OPENAI_TIMEOUT` | `openai.timeout_seconds` | `120` | SDK timeout in seconds |
| `PYVEIL_SECRET` | `pyveil.secret_env` | required | HMAC secret environment variable |
| `PYVEIL_SCOPE` | `pyveil.scope` | `openai/example` | Placeholder namespace |

```bash
python -m pyveil.integrations.openai \
  --config examples/openai.example.yaml \
  --env-file .env
```

YAML may name the environment variables that hold secrets, but direct
`openai.api_key` and `pyveil.secret` fields are rejected.

## Run The Offline SDK Contract

```bash
pip install -e ".[openai,test]"
pytest tests/test_provider_contracts.py -m provider_contract --no-cov
```

The test verifies that the official SDK receives placeholders and that the raw
synthetic email and phone never appear in its serialized request body.

## Boundary Notes

- A custom `OPENAI_BASE_URL` is another trust boundary. pyveil validates the
  URL and rejects embedded credentials, but it cannot evaluate the operator.
- Provider output may contain new sensitive values. Redact it again with
  channel `prompt.output` before logging, persistence, or downstream chaining.
- API calls are billed separately from ChatGPT subscriptions. Dry-run and mock
  contract tests remain network-free and cost-free.
- Older OpenAI model IDs are not a free testing tier and may be retired. Keep
  `OPENAI_MODEL` set to a model currently available to the account.
- Regex and known-value rules do not discover arbitrary names or addresses.
