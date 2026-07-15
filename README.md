# pyveil: PII and secret redaction for Python AI agents

<p align="center">
  <strong>Stop sensitive data before it reaches an LLM, tool, MCP resource, memory store, log, or trace.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/pyveil/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/pyveil?style=flat-square"></a>
  <a href="https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/hyeonsangjeon/pyveil/actions/workflows/tests.yml/badge.svg"></a>
  <a href="https://www.python.org/"><img alt="Python 3.8 to 3.14" src="https://img.shields.io/badge/python-3.8%20to%203.14-3776AB?style=flat-square"></a>
  <img alt="Zero core dependencies" src="https://img.shields.io/badge/core%20dependencies-zero-111827?style=flat-square">
  <img alt="Typed package" src="https://img.shields.io/badge/typed-py.typed-7C3AED?style=flat-square">
  <a href="https://hyeonsangjeon.github.io/pyveil/evaluation.html"><img alt="Synthetic evaluation: 39 cases passing" src="https://img.shields.io/badge/synthetic%20evaluation-39%20cases%20passing-4ade80?style=flat-square"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-green?style=flat-square"></a>
</p>

<p align="center">
  <a href="https://hyeonsangjeon.github.io/pyveil/manual.html">Documentation</a> &middot;
  <a href="https://hyeonsangjeon.github.io/pyveil/guides/">Guides</a> &middot;
  <a href="https://hyeonsangjeon.github.io/pyveil/evaluation.html">Evaluation</a> &middot;
  <a href="https://pypi.org/project/pyveil/">PyPI</a> &middot;
  <a href="https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md">Cookbook</a> &middot;
  <a href="https://github.com/hyeonsangjeon/pyveil/blob/main/docs/redaction-reference.md">Detection reference</a> &middot;
  <a href="https://github.com/hyeonsangjeon/pyveil/discussions">Support</a> &middot;
  <a href="https://github.com/hyeonsangjeon/pyveil/security">Security</a>
</p>

`pyveil` is local, dependency-free redaction middleware for LLM applications and
AI agents. It replaces high-confidence PII and credentials with deterministic,
scoped HMAC placeholders before data crosses an application boundary.

| Raw application context | Context sent to the model |
| --- | --- |
| `Email alice@example.com` | `Email [EMAIL:a13f7c91b0d2]` |
| `api_key: sk-proj-...` | `api_key: [API_KEY:38ded98a17e7]` |
| `Authorization: Bearer ...` | `[AUTH_HEADER:4fe2926b7d20]` |

No network calls. No reversible vault. No raw values in findings by default.

## Try It

```bash
pip install pyveil
pyveil demo
# or: python -m pyveil demo
```

Or run the synthetic demo in an isolated environment:

```bash
uvx pyveil demo
```

```text
before: Email alice@example.com, call 010-1234-5678, and use API key sk-proj-...
after:  Email [EMAIL:...], call [PHONE:...], and use API key [API_KEY:...]
found:  API_KEY, EMAIL, PHONE
```

## Protect An LLM Call

Put `pyveil` immediately before the provider call. The same code works with
OpenAI, Azure OpenAI, Anthropic, Gemini, LiteLLM, or an internal gateway.

```python
from pyveil import Channel, Veil

veil = Veil.high(
    secret=b"tenant-or-run-secret",
    scope="tenant/session",
)

messages = [
    {"role": "user", "content": "Email alice@example.com about my account."},
]

safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
response = call_llm(safe.data)  # Your provider SDK call
```

The provider receives the same list and dictionary shape, with sensitive values
replaced before serialization or transmission.

## Azure OpenAI: End To End

Install the optional Azure example dependencies, then load configuration from
environment variables, `.env`, or YAML:

```bash
pip install "pyveil[azure-openai]"
```

```python
from pyveil.integrations.azure_openai import ask_azure_openai, load_settings

settings = load_settings()  # AZURE_OPENAI_* + PYVEIL_* environment variables
result = ask_azure_openai(
    "Write a follow-up for alice@example.com or 010-1234-5678.",
    settings,
)

print(result.redacted_input)  # The exact text sent to Azure OpenAI
print(result.output_text)     # The model response
```

The integration uses Azure OpenAI's v1 endpoint and Responses API. The
deployment name is passed as `model`; pyveil redacts the prompt before
`client.responses.create(...)` runs.

Prove the boundary without an Azure request:

```bash
PYVEIL_SECRET=docs-demo-secret \
  python -m pyveil.integrations.azure_openai --dry-run
```

```text
mode: dry-run
deployment: not configured
sent-to-azure: Write a one-sentence support follow-up for [EMAIL:347ab11285a3] or [PHONE:548017338f6f].
findings: EMAIL=1, PHONE=1
azure-response: skipped (--dry-run)
```

For a live call, either export `AZURE_OPENAI_ENDPOINT`,
`AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`, `PYVEIL_SECRET`, and
optionally `PYVEIL_SCOPE`, or use the checked-in
[`.env` template](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/azure_openai.env.example)
and [YAML template](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/azure_openai.example.yaml):

```bash
python -m pyveil.integrations.azure_openai --env-file .env
python -m pyveil.integrations.azure_openai \
  --config examples/azure_openai.example.yaml --env-file .env
```

Process environment variables override `.env`, which overrides non-secret YAML
settings. API keys and the pyveil HMAC secret are rejected if placed directly
in YAML; YAML names the environment variables that contain them.

<p align="center">
  <img src="https://raw.githubusercontent.com/hyeonsangjeon/pyveil/main/docs/media/pyveil-awesome-demo.gif"
       alt="pyveil redacts synthetic PII and secrets before an AI agent boundary"
       width="820">
</p>

## Why pyveil

| Need | What pyveil provides |
| --- | --- |
| Keep data local | Standard-library core, zero required dependencies, zero network calls |
| Preserve references | Stable `[TYPE:12hex]` placeholders from HMAC-SHA256 |
| Isolate tenants and runs | Caller-defined `scope` changes placeholders across boundaries |
| Redact real agent payloads | Recursive dictionaries, lists, tuples, and JSON strings |
| Cover more than prompts | Policy channels for tools, MCP, memory, logs, traces, input, and output |
| Stop credentials in tool calls | Auth headers, private keys, API keys, JWTs, and tokens block by default |
| Cover app-specific data | Exact known-value and trusted custom-regex rules |
| Audit without leaking | Findings contain type, rule, path, placeholder, and fingerprint, not raw values |
| Verify supported behavior | Public 39-case synthetic regression corpus, evaluator, and CI gate |

## Reproducible Evidence

The repository ships a public synthetic detector corpus and a standard-library
evaluator:

```bash
python evaluation/evaluate.py --check
```

For corpus v1, pyveil 0.2.1 matches all 36 expected findings across 39 cases
(33 positive, 6 negative), with no corpus false positives, false negatives,
labeled-value leaks, or non-empty `Finding.raw` values.

These numbers describe documented supported shapes only. They are **not** a
real-world PII recall benchmark and do not cover unknown names, addresses,
languages, documents, or images. Read the
[methodology and limits](https://hyeonsangjeon.github.io/pyveil/evaluation.html).

## Known Names And Domain IDs

Regex cannot discover arbitrary names or addresses. When your application
already knows a value is sensitive, teach that value to `pyveil` without adding
an NER model:

```python
from pyveil import CustomRule, Veil

rules = [
    CustomRule.exact("PERSON", ["Alice Kim", "Hong Gildong"]),
    CustomRule("CUSTOMER_ID", r"\bCUS-[A-Z0-9]{8}\b", rule_id="customer_id"),
]

veil = Veil.high(
    secret=b"tenant-secret",
    scope="tenant/session",
    rules=rules,
)

result = veil.redact_text("Alice Kim owns CUS-A1B2C3D4.")
print(result.text)
# [PERSON:...] owns [CUSTOMER_ID:...].
```

Custom patterns are trusted application code. Keep them narrow and test them
against realistic positive and negative samples.

## Agent Boundaries

Classic masking often stops at text input. Agents move data across several
surfaces, so channels are first-class policy inputs:

| Channel | Redact before |
| --- | --- |
| `prompt.input` | User, RAG, or application context reaches a model |
| `prompt.output` | Model output is displayed or chained |
| `tool.call.arguments` | A model-controlled tool executes |
| `tool.call.result` | Tool output returns to a model |
| `mcp.resource.content` | MCP resource content enters context |
| `memory.write` | Text is embedded or persisted |
| `trace.span.attributes` | Attributes leave through telemetry |
| `log.record` | Records reach handlers or external sinks |

```text
user / retrieval / tool / resource data
                    |
                  pyveil
                    |
model / tool / MCP / memory / trace / log boundary
```

## Detection Board

Core detection is intentionally conservative and high precision:

| Type | Examples | HIGH output |
| --- | --- | --- |
| `EMAIL` | Email addresses | `[EMAIL:12hex]` |
| `PHONE` | Korean, separated international, and compact E.164 phone shapes | `[PHONE:12hex]` |
| `CREDIT_CARD` | Card numbers that pass Luhn validation | `[CREDIT_CARD:12hex]` |
| `JWT` | Compact JSON Web Tokens | `[JWT:12hex]` |
| `AUTH_HEADER` | Bearer and Basic authorization headers | `[AUTH_HEADER:12hex]` |
| `PRIVATE_KEY` | PEM private-key blocks | `[PRIVATE_KEY:12hex]` |
| `API_KEY` | OpenAI, GitHub, Slack, Google, and AWS-style keys | `[API_KEY:12hex]` |
| `URL_QUERY_SECRET` | Token, key, secret, code, and auth query values | `[URL_QUERY_SECRET:12hex]` |
| `KV_SECRET` | Password, cookie, secret, and token key-value pairs | `[KV_SECRET:12hex]` |
| Custom | Known values and application regex rules | `[YOUR_TYPE:12hex]` |

See the [full redaction reference](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/redaction-reference.md)
for examples, validation rules, LOW masking output, and limitations.

## HIGH And LOW

Use `HIGH` at model, agent, tool, MCP, memory, trace, and external log
boundaries. It produces stable HMAC placeholders such as
`[EMAIL:a13f7c91b0d2]`.

Use `LOW` only for human-facing previews where preserving shape is useful:

```text
alice@example.com  -> al***@e******.com
010-1234-5678      -> 010-****-5678
4242 4242 4242 4242 -> **** **** **** 4242
```

Credential-like values remain aggressively hidden in both levels.

## Policy

The default high policy redacts supported findings and blocks credentials in
`tool.call.arguments`:

```python
from pyveil import Action, Channel, Entity, Policy, Veil

policy = Policy.default_high().override(
    Channel.PROMPT_INPUT,
    Entity.EMAIL,
    Action.PASS,
)

veil = Veil.high(secret=b"tenant-secret", policy=policy)
```

When both `policy` and `level` are supplied, the explicit policy decides channel
levels and actions. Build one `Veil` per tenant, session, or run and reuse it.

## CLI

Use stdin for shell pipelines, files for preflight checks, and JSON output for
structured automation:

```bash
export PYVEIL_SECRET="tenant-or-run-secret"
export PYVEIL_SCOPE="tenant/session"

printf 'Email alice@example.com' | pyveil redact -
pyveil redact request.json --channel tool.call.result --format json
pyveil scan prompt.txt --format json
pyveil init
pyveil test-config pyveil.yaml
```

`scan` emits finding metadata without raw sensitive values. JSON-shaped input
is parsed and traversed structurally.

## Integration Recipes

| Stack or boundary | Copy-paste example |
| --- | --- |
| Any LLM provider | [Provider-neutral client wrapper](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/llm_client_boundary.py) |
| OpenAI Agents SDK | [Input guardrail example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/openai_agents_guardrail.py) |
| Azure OpenAI | [Runnable env/YAML integration](https://github.com/hyeonsangjeon/pyveil/blob/main/pyveil/integrations/azure_openai.py) and [short example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/azure_openai.py) |
| LiteLLM | [Proxy filter example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/litellm_proxy_filter.py) |
| FastAPI | [Request middleware example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/fastapi_middleware.py) |
| MCP | [Server wrapper](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/mcp_server_wrapper.py) and [integration guide](https://hyeonsangjeon.github.io/pyveil/manual.html#integrations) |
| Python logging | [Logging filter example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/log_filter.py) |
| Agent memory | [Before-embedding example](https://github.com/hyeonsangjeon/pyveil/blob/main/examples/memory_write.py) |

The [cookbook](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/cookbook.md)
covers prompts, tools, MCP, memory, logging, tracing, JSON, and CLI workflows.

## Pick The Right Tool

Choose `pyveil` when you want a small local boundary filter for structured PII,
credentials, known values, and domain identifiers across agent context flows.

Choose Presidio, GLiNER, or another NER-backed system when you need broad
semantic discovery of unknown people, organizations, locations, or addresses.
Choose an enterprise DLP product when you need managed policy, document/image
coverage, incident workflows, or compliance reporting.

These tools can be layered. `pyveil` does not claim perfect recall.
See the full [pyveil vs Presidio, NER, guardrails, and DLP decision guide](https://hyeonsangjeon.github.io/pyveil/guides/pyveil-vs-presidio.html).

## Safety Contract

- Raw sensitive values are not stored in `Finding` objects by default.
- Placeholders use HMAC-SHA256 with a caller-provided secret and scope.
- Credential-like values can be blocked before model-controlled tools execute.
- `max_input_chars` bounds work performed on text and structured payloads.
- The core makes no network calls and has no required third-party dependency.
- pyveil has no reversible vault or unmasking API.

`pyveil` is not a compliance guarantee, enterprise DLP system, secret-scanning
replacement, or prompt-injection firewall. Read the
[threat model](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/threat-model.md),
[known limitations](https://github.com/hyeonsangjeon/pyveil/blob/main/docs/known-limitations.md),
and [security policy](https://github.com/hyeonsangjeon/pyveil/blob/main/SECURITY.md)
before production use.

## Guides

- [Complete manual](https://hyeonsangjeon.github.io/pyveil/manual.html)
- [Python LLM PII redaction guide](https://hyeonsangjeon.github.io/pyveil/guides/python-llm-pii-redaction.html)
- [MCP PII redaction guide](https://hyeonsangjeon.github.io/pyveil/guides/mcp-pii-redaction.html)
- [pyveil vs Presidio / NER / DLP](https://hyeonsangjeon.github.io/pyveil/guides/pyveil-vs-presidio.html)
- [Reproducible detector evaluation](https://hyeonsangjeon.github.io/pyveil/evaluation.html)
- [English video guide](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.2/pyveil-usage-guide-en.mp4)
- [Korean video guide](https://github.com/hyeonsangjeon/pyveil/releases/download/v0.1.2/pyveil-usage-guide-ko.mp4)
- [AGENTS.md](https://github.com/hyeonsangjeon/pyveil/blob/main/AGENTS.md) for coding agents
- [llms.txt](https://hyeonsangjeon.github.io/pyveil/llms.txt) for LLM-readable navigation
- [Contributing](https://github.com/hyeonsangjeon/pyveil/blob/main/CONTRIBUTING.md)

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
uv run --extra test python evaluation/evaluate.py --check
```

CI runs the test suite on Python `3.8` through `3.14`. The core remains typed,
dependency-free, and MIT licensed.
