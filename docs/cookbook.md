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

## 2. Azure OpenAI Or OpenAI-Compatible Adapter

pyveil does not need to know which provider is behind the client. Keep the provider-specific code inside `call_llm`.

```python
from typing import Dict, List, cast

from pyveil import Channel, Veil

Message = Dict[str, str]


def safe_chat(messages: List[Message]) -> str:
    veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/session-456")
    safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
    return call_llm_provider(cast(List[Message], safe.data))


def call_llm_provider(messages: List[Message]) -> str:
    # Example shape only:
    #
    # response = client.chat.completions.create(
    #     model=deployment_or_model_name,
    #     messages=messages,
    # )
    # return response.choices[0].message.content
    #
    # Use the same function body for Azure OpenAI, OpenAI-compatible gateways,
    # or your internal proxy. pyveil stays one layer above the provider.
    return "replace with provider response"
```

## 3. Block Credentials Before Model-Controlled Tool Calls

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

## 4. Redact Tool Results Before Returning Them To The Model

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

## 5. Redact MCP Resource Content

MCP resources can expose files, database rows, logs, or API payloads. Redact before the resource content enters an agent context.

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/mcp")


def read_resource_for_agent(resource_id: str) -> object:
    raw_resource = read_resource(resource_id)
    return veil.redact_data(raw_resource, channel=Channel.MCP_RESOURCE_CONTENT).data
```

## 6. Redact Memory Before Embedding Or Persistence

Memory stores create long-lived recall. Redact before embedding and before persistence.

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant-123/memory")


def write_memory(text: str) -> None:
    safe = veil.redact_text(text, channel=Channel.MEMORY_WRITE)
    embedding = embed(safe.text)
    memory_store.save(text=safe.text, embedding=embedding)
```

## 7. Redact Logs Before Export

Use the built-in logging integration for application logs.

```python
import logging

from pyveil import Veil
from pyveil.integrations import PyVeilLogFilter

logger = logging.getLogger("app")
logger.addFilter(PyVeilLogFilter(Veil.high(secret=b"log-secret", scope="prod/logs")))

logger.warning("failed request for alice@example.com")
```

## 8. CLI Preflight In CI Or Local Scripts

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

## 9. Redact Known Names And Domain Identifiers

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
