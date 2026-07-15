# pyveil Cookbook

Copy-paste recipes for putting pyveil in front of model, tool, MCP, memory, log, and trace boundaries.

The core rule is simple:

```text
raw context -> pyveil -> model/tool/memory/log/trace
```

Use `HIGH` for agent-facing or provider-facing boundaries. Use `LOW` only for human-facing diagnostic previews.

## 1. Redact Before Any LLM Client

Keep pyveil outside the provider-specific client. OpenAI, Azure OpenAI, Anthropic, Gemini, LiteLLM, and internal gateways can all use the same boundary shape.

```python
from typing import Callable, Dict, List, cast

from pyveil import Channel, Veil

Message = Dict[str, str]
LLMCall = Callable[[List[Message]], str]


def call_with_redaction(messages: List[Message], call_llm: LLMCall) -> str:
    veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/session-456")
    safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
    return call_llm(cast(List[Message], safe.data))


def call_llm(messages: List[Message]) -> str:
    # Replace this function with your provider SDK call.
    return "provider received: " + messages[-1]["content"]


response = call_with_redaction(
    [
        {"role": "system", "content": "You are concise."},
        {
            "role": "user",
            "content": "Email alice@example.com about API key sk-proj-abcdefghijklmnopqrstuvwxyz123456.",
        },
    ],
    call_llm,
)

print(response)
```

## 2. Ollama With A Memory-Aware Local Model

Install the optional dependencies and pull the recommended 16GB-Mac model:

```bash
pip install "pyveil[ollama]"
ollama pull qwen3.5:4b
```

The helper redacts before `Client.chat(...)` and returns the exact local-model
input, response text, and available timing/token metrics:

```python
from pyveil.integrations.ollama import ask_ollama, load_settings


def answer_with_ollama(prompt: str) -> str:
    settings = load_settings()
    result = ask_ollama(prompt, settings)
    print("sent-to-ollama:", result.redacted_input)
    print("total-ms:", result.total_duration_ms)
    return result.output_text or ""


answer = answer_with_ollama(
    "Write a follow-up for alice@example.com or 010-1234-5678."
)
```

Under the hood, the boundary stays deliberately small:

```python
from ollama import Client
from pyveil import Channel, Veil

client = Client(host=settings.host, timeout=settings.timeout_seconds)
veil = Veil.high(
    secret=settings.pyveil_secret,
    scope=settings.pyveil_scope,
)

safe = veil.redact_text(prompt, channel=Channel.PROMPT_INPUT)
response = client.chat(
    model=settings.model,
    messages=[{"role": "user", "content": safe.text}],
    stream=False,
    think=False,
    options={"num_ctx": 4096, "num_predict": 128, "temperature": 0.2},
    keep_alive="0",
)
```

Try the non-model and live paths:

```bash
export PYVEIL_SECRET="a-long-random-hmac-secret"

python -m pyveil.integrations.ollama --dry-run
python -m pyveil.integrations.ollama
python -m pyveil.integrations.ollama \
  --config examples/ollama.example.yaml --env-file .env
```

Configuration priority is process environment, `.env`, YAML, then defaults.
The default `qwen3.5:4b` configuration uses a 4096-token context and
`keep_alive=0` to release memory after each response. Use
`OLLAMA_KEEP_ALIVE=5m` when repeated-call latency matters more than reclaiming
roughly 3.2GB immediately on a 16GB Apple silicon Mac.

Dry-run output from the synthetic default prompt:

```text
mode: dry-run
model: qwen3.5:4b
host: http://127.0.0.1:11434
sent-to-ollama: Write a one-sentence support follow-up for [EMAIL:71c6727a7fa2] or [PHONE:b4b889df07ce].
findings: EMAIL=1, PHONE=1
ollama-response: skipped (--dry-run)
```

See [`pyveil/integrations/ollama.py`](../pyveil/integrations/ollama.py),
[`examples/ollama.env.example`](../examples/ollama.env.example),
[`examples/ollama.example.yaml`](../examples/ollama.example.yaml), and the
[full Ollama integration guide](integrations/ollama.md).

## 3. Azure OpenAI With Environment Or YAML Configuration

Install the optional dependencies:

```bash
pip install "pyveil[azure-openai]"
```

The installable helper uses the Azure OpenAI v1 endpoint and Responses API. It
returns both the exact redacted input sent to Azure and the model output:

```python
from pyveil.integrations.azure_openai import ask_azure_openai, load_settings


def answer_with_azure(prompt: str) -> str:
    settings = load_settings()
    result = ask_azure_openai(prompt, settings)
    print("sent-to-azure:", result.redacted_input)
    return result.output_text or ""


answer = answer_with_azure(
    "Write a follow-up for alice@example.com or 010-1234-5678."
)
```

Under the hood, the provider boundary is deliberately small:

```python
from openai import OpenAI
from pyveil import Channel, Veil

client = OpenAI(
    api_key=settings.api_key,
    base_url=settings.endpoint.rstrip("/") + "/openai/v1/",
)
veil = Veil.high(
    secret=settings.pyveil_secret,
    scope=settings.pyveil_scope,
)

safe = veil.redact_text(prompt, channel=Channel.PROMPT_INPUT)
response = client.responses.create(
    model=settings.deployment,  # Azure deployment name
    input=safe.text,            # Raw prompt never enters this call
)
```

Use environment variables directly:

```bash
export AZURE_OPENAI_ENDPOINT="https://YOUR-RESOURCE-NAME.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT="YOUR_DEPLOYMENT_NAME"
export AZURE_OPENAI_API_KEY="..."
export PYVEIL_SECRET="a-long-random-hmac-secret"
export PYVEIL_SCOPE="tenant-123/session-456"

python -m pyveil.integrations.azure_openai --dry-run
python -m pyveil.integrations.azure_openai
```

Or load `.env` and non-secret YAML settings:

```bash
python -m pyveil.integrations.azure_openai --env-file .env
python -m pyveil.integrations.azure_openai \
  --config examples/azure_openai.example.yaml --env-file .env
```

Configuration priority is process environment, `.env`, YAML, then defaults.
YAML may contain endpoint, deployment, scope, and the names of secret-bearing
environment variables. Plaintext `api_key` and `secret` YAML fields are
rejected.

Dry-run output from the synthetic default prompt:

```text
mode: dry-run
deployment: not configured
sent-to-azure: Write a one-sentence support follow-up for [EMAIL:347ab11285a3] or [PHONE:548017338f6f].
findings: EMAIL=1, PHONE=1
azure-response: skipped (--dry-run)
```

See [`pyveil/integrations/azure_openai.py`](../pyveil/integrations/azure_openai.py),
[`examples/azure_openai.env.example`](../examples/azure_openai.env.example), and
[`examples/azure_openai.example.yaml`](../examples/azure_openai.example.yaml).

## 4. Block Credentials Before Model-Controlled Tool Calls

The default policy blocks credential-like material in `tool.call.arguments`.

```python
from pyveil import BlockedSensitiveData, Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/run-789")

tool_args = {
    "url": "https://api.example.test/accounts",
    "headers": {"Authorization": "Bearer synthetic-token-value"},
}

try:
    safe_args = veil.redact_data(tool_args, channel=Channel.TOOL_CALL_ARGUMENTS).data
except BlockedSensitiveData as exc:
    # Do not execute the tool with raw credentials.
    print(exc)
else:
    run_tool(**safe_args)
```

## 5. Redact Tool Results Before Returning Them To The Model

Tool results often contain customer records, logs, URLs, headers, or hidden tokens.

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/tool-result")

raw_result = {
    "owner": "alice@example.com",
    "callback": "https://example.test/callback?access_token=synthetic-token&state=ok",
}

safe_result = veil.redact_data(raw_result, channel=Channel.TOOL_CALL_RESULT).data
```

## 6. Redact MCP Resource Content

MCP resources can expose files, database rows, logs, or API payloads. Redact before the resource content enters an agent context.

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/mcp")


def read_resource_for_agent(resource_id: str) -> object:
    raw_resource = read_resource(resource_id)
    return veil.redact_data(raw_resource, channel=Channel.MCP_RESOURCE_CONTENT).data
```

## 7. Redact Memory Before Embedding Or Persistence

Memory stores create long-lived recall. Redact before embedding and before persistence.

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/memory")


def write_memory(text: str) -> None:
    safe = veil.redact_text(text, channel=Channel.MEMORY_WRITE)
    embedding = embed(safe.text)
    memory_store.save(text=safe.text, embedding=embedding)
```

## 8. Redact Logs Before Export

Use the built-in logging integration for application logs.

```python
import logging

from pyveil import Veil
from pyveil.integrations import PyVeilLogFilter

logger = logging.getLogger("app")
logger.addFilter(PyVeilLogFilter(Veil.high(secret=b"log-secret", scope="prod/logs")))

logger.warning("failed request for alice@example.com")
```

## 9. CLI Preflight In CI Or Local Scripts

Use `pyveil scan` to count findings and `pyveil redact` to create a redacted artifact.

```bash
export PYVEIL_SECRET="tenant-or-run-secret"
export PYVEIL_SCOPE="tenant/session"

pyveil demo
printf 'Email alice@example.com' | pyveil redact -
pyveil scan prompt.txt --format json
pyveil redact prompt.txt --channel prompt.input > prompt.safe.txt
pyveil redact request.json --channel tool.call.result --format json > request.safe.json
```

## 10. Redact Known Names And Domain Identifiers

The dependency-free core does not guess unknown names. Add values that your
application already knows are sensitive, plus narrow identifiers from your own
domain:

```python
from pyveil import CustomRule, Veil

rules = [
    CustomRule.exact("PERSON", ["Alice Kim", "Hong Gildong"]),
    CustomRule("ACCOUNT_ID", r"\bACC-[A-Z0-9]{10}\b", rule_id="account_id"),
]

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session", rules=rules)
safe = veil.redact_text(
    "Alice Kim requested access to ACC-A1B2C3D4E5.",
    channel="prompt.input",
)
```

Do not build a regex from untrusted pattern input. Treat custom patterns as
application code and test both matches and non-matches.

## Boundary Checklist

| Boundary | Recommended channel |
| --- | --- |
| User prompt or retrieved context before model input | `prompt.input` |
| Model output before display or chaining | `prompt.output` |
| Tool arguments before execution | `tool.call.arguments` |
| Tool result before returning to the model | `tool.call.result` |
| MCP resource content before agent use | `mcp.resource.content` |
| Memory text before embedding or persistence | `memory.write` |
| Trace attributes before export | `trace.span.attributes` |
| Application log record before handlers or sinks | `log.record` |

## What To Avoid

- Do not ask the model to redact secrets after the model has already seen them.
- Do not expose an unmasking tool to an agent.
- Do not reuse one `scope` across tenants when linkability matters.
- Do not treat redaction as a compliance guarantee.
- Do not send blocked `tool.call.arguments` through the tool anyway.
