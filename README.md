# pyveil

**Redact PII and secrets before sending Python data to an LLM.**

[![PyPI](https://img.shields.io/pypi/v/pyveil?style=flat-square)](https://pypi.org/project/pyveil/)
[![Tests](https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml/badge.svg)](https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml)
[![Python 3.8 to 3.14](https://img.shields.io/badge/python-3.8%20to%203.14-3776AB?style=flat-square)](https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml)
[![Zero core dependencies](https://img.shields.io/badge/core%20dependencies-zero-111827?style=flat-square)](https://github.com/hyeonsangjeon/pyveil/blob/main/pyproject.toml)
[![MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/hyeonsangjeon/pyveil/blob/main/LICENSE)

[Quickstart](#quickstart) · [OpenAI Agents / LiteLLM](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/openai-agents-vs-litellm.md) · [Manual](https://hyeonsangjeon.github.io/pyveil/manual.html) · [Detection reference](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/redaction-reference.md) · [Security](https://github.com/hyeonsangjeon/pyveil/blob/main/SECURITY.md)

Keep email addresses, phone numbers, and supported credentials out of model
requests, tool results, MCP resources, memory, logs, and traces. pyveil runs
locally, preserves JSON-shaped payloads, and needs **no model, API key, or
runtime dependency**. You call it before each boundary you want to protect;
installing it does not automatically intercept SDK calls.

## Quickstart

Requires Python 3.8+. In your Python environment:

```bash
python -m pip install pyveil
```

Run this complete example. It makes no provider request:

<!-- quickstart:python -->
```python
import secrets

from pyveil import Channel, Veil

veil = Veil.high(secret=secrets.token_bytes(32), scope="support/session-42")
messages = [
    {"role": "user", "content": "Email alice@example.com about ticket 42."},
]
safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
print(safe.data[0]["content"])
```
<!-- /quickstart:python -->

Output shape (the 12-hex suffix depends on your key and scope):

```text
Email [EMAIL:...] about ticket 42.
```

Pass **`safe.data`**, not `messages`, to your SDK. The original input is unchanged;
message roles and ticket `42` are preserved. For plain strings use
`veil.redact_text(text).text`.

This example creates a random key once per run. Reuse the same `Veil` within a
session; load a private, stable secret from your environment or secret manager
when placeholders must survive restarts. Never reuse a documentation secret
with real data. [Key and scope guidance](https://hyeonsangjeon.github.io/pyveil/manual.html#placeholders)

## Start With Your Integration

| Your stack | Start here | What runs locally |
| --- | --- | --- |
| OpenAI Agents SDK | [Runner wrapper and setup](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/openai-agents-vs-litellm.md#openai-agents-sdk) | Redacts initial input **before** `Runner.run`; keyless checkout example |
| LiteLLM SDK / Proxy | [SDK wrapper and Proxy hook](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/openai-agents-vs-litellm.md#litellm-proxy) | Redacts completion `messages` before dispatch; keyless checkout example |
| OpenAI Responses API | [Installable helper](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/openai.md) | `python -m pyveil.integrations.openai --dry-run` |
| Anthropic / Claude | [Installable helper](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/anthropic.md) | `python -m pyveil.integrations.anthropic --dry-run` |
| Azure OpenAI | [Env / YAML setup](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md#5-azure-openai-with-environment-or-yaml-configuration) | `python -m pyveil.integrations.azure_openai --dry-run` |
| Ollama | [Local model guide](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/ollama.md) | `python -m pyveil.integrations.ollama --dry-run` |
| MCP, logs, memory, FastAPI | [Cookbook](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md) | Explicit wrappers at your application's boundaries |

Provider dry-runs require `PYVEIL_SECRET`; the linked guides cover configuration
and optional SDK dependencies for live calls. Dry-runs are **not model responses**.
OpenAI Agents input guardrails validate or block; they do not replace the input,
so the example redacts before dispatch. The LiteLLM Proxy hook covers
list-valued `messages`, not every endpoint or payload field.

**Examples vs installed modules:** `pyveil.integrations.*` ships in the wheel.
`examples/*.py` does not. To run the OpenAI Agents and LiteLLM recipes without
either SDK or a provider key, start from a checkout:

```bash
git clone https://github.com/hyeonsangjeon/pyveil.git
cd pyveil
python -m pip install .
python examples/openai_agents_guardrail.py
python examples/litellm_proxy_filter.py
```

Use a virtual environment for installation. See the
[comparison guide](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/openai-agents-vs-litellm.md#run-both-without-keys)
for macOS/Linux and Windows setup, expected output, and bypass risks.

## What Gets Redacted?

HIGH replaces supported findings with `[TYPE:12hex]` HMAC placeholders. The same
value, type, key, and scope produce the same placeholder, so repeated references
remain linkable within your chosen scope.

| Type | Supported shapes |
| --- | --- |
| `EMAIL` | Email addresses |
| `PHONE` | Korean, separated international, and compact E.164 shapes |
| `CREDIT_CARD` | Candidate card numbers that pass Luhn validation |
| `JWT` | Compact JSON Web Tokens |
| `AUTH_HEADER` | Bearer and Basic authorization headers |
| `PRIVATE_KEY` | PEM private-key blocks |
| `API_KEY` | Supported OpenAI, GitHub, Slack, Google, and AWS-style patterns |
| `URL_QUERY_SECRET` | Supported secret-bearing URL query parameters |
| `KV_SECRET` | Sensitive key-value pairs, including passwords and tokens |
| Custom rules | Exact known values and trusted application regexes |

Unknown names, addresses, images, and documents are **not** automatically
detected. Use `CustomRule.exact(...)` for known values, or add a separate semantic
detection layer. The [detection board](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/redaction-reference.md)
shows inputs, HIGH/LOW outputs, validation rules, and limits.

Use **HIGH** for model-facing data. **LOW** is a human-facing preview, such as
`al***@e******.com`; it deliberately retains identifying shape. Credentials stay
aggressively hidden in both levels. pyveil is not a compliance guarantee,
prompt-injection firewall, DLP suite, or reversible vault.

## Protect More Than Prompts

| Task | Channel | Example |
| --- | --- | --- |
| Prepare model input / output | `prompt.input`, `prompt.output` | [Provider-neutral boundary](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/llm_client_boundary.py) |
| Block credentials in tool arguments | `tool.call.arguments` | [Blocking recipe](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md#6-block-credentials-before-model-controlled-tool-calls) |
| Redact tool results / MCP resources | `tool.call.result`, `mcp.resource.content` | [MCP wrapper](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/mcp_server_wrapper.py) |
| Redact before embedding or persistence | `memory.write` | [Memory example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/memory_write.py) |
| Redact before telemetry export | `log.record`, `trace.span.attributes` | [Logging](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/logging.md) / [tracing](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/integrations/tracing.md) |

The default policy raises `BlockedSensitiveData` for credential-like findings in
`tool.call.arguments`. On failure, **do not dispatch the original payload**.
Findings omit raw sensitive values by default; your application's original
objects still exist in memory. [Policy and failure handling](https://hyeonsangjeon.github.io/pyveil/manual.html#policy)

## Process A File

From an empty working directory after installation:

```bash
python -m pyveil init --example
python -m pyveil run
```

This creates synthetic input, `pyveil.json`, and a random private `.pyveil.key`,
then writes real redacted output and a receipt under `.pyveil-runs/<run-id>/`.
No model is called. Run twice with unchanged input, config, key, and version for
identical output bytes in separate directories.

For your own file, use the following instead of `init --example`:

```bash
python -m pyveil init --input /path/to/request.json --input-format json
```

Keep keys and outputs out of Git; redacted output is not automatically safe to
publish. [Configuration, Windows commands, error codes, and migration](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/file-runs.md)

## Verify Before You Integrate

One installed command exercises six synthetic agent boundaries without keys:

```bash
python -m pyveil replay --format markdown
```

The current regression expectation is **6/6 passing cases, 10 findings, and
0 surviving labeled synthetic markers**. It checks benign fields, structure,
and a second redaction pass. It is not a real-world PII recall benchmark.
[Replay methodology and limits](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/privacy-replay.md)

CI tests Python 3.8 through 3.14, installs built wheels in clean environments,
executes the quickstart above, and verifies file runs. Separate offline tests
inspect official OpenAI and Anthropic SDK request bodies through local mock
transports; they do not claim live paid API validation.

[Test runs](https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml) ·
[39-case detector corpus](https://hyeonsangjeon.github.io/pyveil/evaluation.html) ·
[Protection-surface contract](https://github.com/hyeonsangjeon/pyveil/blob/main/compatibility/README.md)

<details>
<summary>Watch the synthetic redaction demo</summary>

![pyveil redacting synthetic agent context](https://raw.githubusercontent.com/hyeonsangjeon/pyveil/main/docs/media/pyveil-awesome-demo.gif)

[English video](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.2/pyveil-usage-guide-en.mp4) ·
[Korean video](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.2/pyveil-usage-guide-ko.mp4)
(v0.1.2 walkthroughs; current CLI setup is in the manual).

</details>

## Documentation And Support

- [Manual](https://hyeonsangjeon.github.io/pyveil/manual.html), [cookbook](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md), and [troubleshooting](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/faq.md)
- [Threat model](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/threat-model.md), [known limitations](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/known-limitations.md), and [security policy](https://github.com/hyeonsangjeon/pyveil/blob/main/SECURITY.md)
- [pyveil vs Presidio / NER / DLP](https://hyeonsangjeon.github.io/pyveil/guides/pyveil-vs-presidio.html)
- [Ask an integration question](https://github.com/hyeonsangjeon/pyveil/discussions) or [report a bug](https://github.com/hyeonsangjeon/pyveil/issues/new/choose). Share synthetic inputs, not real PII or credentials.
- [AGENTS.md](https://github.com/hyeonsangjeon/pyveil/blob/main/AGENTS.md) and [llms.txt](https://hyeonsangjeon.github.io/pyveil/llms.txt) for coding agents

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
uv run --extra test python evaluation/evaluate.py --check
```

[Contributing](https://github.com/hyeonsangjeon/pyveil/blob/main/CONTRIBUTING.md) ·
[Changelog](https://github.com/hyeonsangjeon/pyveil/blob/main/CHANGELOG.md) ·
[Maintainer traffic measurements](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/maintainer-metrics.md)
