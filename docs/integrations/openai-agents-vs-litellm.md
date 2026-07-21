# OpenAI Agents SDK vs LiteLLM Redaction Boundaries

The OpenAI Agents and LiteLLM examples enforce the same invariant at different
integration points:

```text
raw application input
        -> pyveil HIGH redaction on prompt.input
        -> same-shaped input with HMAC placeholders
        -> agent runtime, LiteLLM SDK, or LiteLLM Proxy
```

Both examples are local and keyless by default. A live provider call remains an
explicit application decision.

These files are repository recipes, not importable modules installed by the
pyveil wheel. Run them from a repository checkout, or copy the small wrapper
you need into your application and keep its contract test.

## Side-by-side Contract

| Contract | OpenAI Agents SDK | LiteLLM Python SDK | LiteLLM Proxy |
| --- | --- | --- | --- |
| Example | [`openai_agents_guardrail.py`](../../examples/openai_agents_guardrail.py) | [`litellm_proxy_filter.py`](../../examples/litellm_proxy_filter.py) | [`litellm_proxy_filter.py`](../../examples/litellm_proxy_filter.py) |
| Detection point | Inside `run_agent_redacted`, before `Runner.run` | Inside `completion_with_redaction`, before `litellm.completion` | Inside `async_pre_call_hook`, before provider dispatch |
| Input inspected | String or list/dictionary agent input | `messages: list[dict]` | `data["messages"]` when it is a list |
| Provider-bound output | Same input shape with supported values replaced | Same message-list shape with supported values replaced | A shallow payload copy whose `messages` value is replaced with a redacted list |
| pyveil channel | `prompt.input` | `prompt.input` | `prompt.input` |
| Secret and scope | Caller supplies a configured `Veil` | Caller supplies a configured `Veil` | `PYVEIL_SECRET` and optional `PYVEIL_SCOPE`, unless a `Veil` is injected |
| Keyless proof | Run the file; the provider call is skipped | Run the file; the provider call is skipped | Contract test invokes the hook directly without starting a proxy |
| Failure before dispatch | Detection, policy, or input-limit exceptions propagate before `Runner.run` | Exceptions propagate before `completion(...)` | Exceptions propagate to LiteLLM; LiteLLM owns the resulting proxy response |
| Main bypass risk | Calling `Runner.run` directly skips this wrapper | Calling `litellm.completion` directly skips this wrapper | Requests that do not contain a list-valued `messages` field pass through unchanged |
| Current boundary limit | Covers the input supplied to this wrapper, not later tool results, memory writes, logs, or traces | Covers completion messages supplied to this wrapper, not other LiteLLM APIs | Does not redact embeddings, images, audio, arbitrary pass-through bodies, or non-message fields |

## Run Both Without Keys

From a repository checkout, install only pyveil to exercise the local
transformations:

```bash
pip install pyveil
python examples/openai_agents_guardrail.py
python examples/litellm_proxy_filter.py
```

Representative output:

```text
sent-to-agent:   ... Email [EMAIL:...] ...
sent-to-litellm: ... Email [EMAIL:...] ...
provider-response: skipped (keyless boundary demo)
```

The exact HMAC suffix differs by scope. The raw synthetic email is not present
in either provider-bound value.

## OpenAI Agents SDK

Install the current upstream SDK on a supported Python version, then route all
initial agent input through the wrapper:

```python
from agents import Agent

from examples.openai_agents_guardrail import run_agent_redacted
from pyveil import Veil

agent = Agent(name="Support", instructions="Answer concisely.")
veil = Veil.high(secret=b"tenant-secret", scope="tenant/session")

result = await run_agent_redacted(
    agent,
    "Email alice@example.com about my case.",
    veil=veil,
)
```

OpenAI Agents input guardrails validate or trip on input; they are not an input
replacement mechanism. pyveil therefore redacts before calling `Runner.run`
instead of treating an SDK guardrail as a sanitizer.

## LiteLLM SDK

Pass the provider call into the wrapper or let the example import
`litellm.completion` lazily:

```python
from litellm import completion

from examples.litellm_proxy_filter import completion_with_redaction
from pyveil import Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session")
response = completion_with_redaction(
    model="your-provider/your-model",
    messages=[{"role": "user", "content": "Email alice@example.com."}],
    veil=veil,
    completion=completion,
)
```

This is opt-in. A direct call to `litellm.completion(...)` is outside pyveil's
boundary.

## LiteLLM Proxy

Make the repository or copied callback module importable by the proxy process,
then register the module-level hook:

```yaml
litellm_settings:
  callbacks: examples.litellm_proxy_filter.proxy_handler_instance
```

```bash
export PYVEIL_SECRET="a-long-random-hmac-secret"
export PYVEIL_SCOPE="tenant/proxy"
litellm --config litellm_config.yaml
```

The example intentionally handles completion-style `messages` only. Add a
separate, tested boundary for every additional endpoint or payload field your
proxy accepts.

## Shared Detection Scope

These integrations use pyveil's conservative built-in detectors for email,
phone numbers, Luhn-valid cards, JWTs, authorization headers, private keys,
high-signal API keys, URL query secrets, and sensitive key-value shapes. Known
application values can be added with `CustomRule`.

They do not discover arbitrary people, organizations, locations, addresses,
documents, or images. They are not compliance guarantees, enterprise DLP, or
prompt-injection defenses. Read the [redaction reference](../redaction-reference.md),
[known limitations](../known-limitations.md), and [security policy](../../SECURITY.md)
before using either boundary with production data.

## Verification

The repository contract tests assert that:

- raw input remains unchanged in application memory
- the value handed to the fake SDK or Proxy hook contains no raw email or phone
- message roles and list/dictionary structure are preserved
- the Proxy hook returns a redacted payload copy

Run them with:

```bash
pytest tests/test_integration_examples.py
```

On 2026-07-22, the import and hook contracts were also smoke-tested locally
against OpenAI Agents SDK 0.18.3 and LiteLLM 1.93.0 on Python 3.10. Those are
verification coordinates, not dependency pins or future compatibility claims.
