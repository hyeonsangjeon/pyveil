# Privacy Boundary Replay

`pyveil replay` is a deterministic, offline proof that the installed package
can apply its public redaction API at six common agent boundaries:

- prompt input before a model call
- tool-call arguments before execution
- MCP resource content before context assembly
- memory content before persistence or embedding
- log records before handlers or external sinks
- trace attributes before export

It is a verification tour, not a scanner for your production data. The command
uses only built-in synthetic fixtures, makes no network calls, needs no API key,
and never prints a fixture input or redacted payload.

## Run It

From a source checkout:

```bash
python -m pyveil replay --format markdown
# same path through the example file:
uv run python examples/privacy_replay.py --format markdown
```

After installing a wheel built from this checkout, the same replay is available
through the package CLI:

```bash
pyveil replay --format json
```

The command exits with `0` only when all six cases pass. A normal run reports
six boundaries, six passing cases, zero surviving synthetic markers, preserved
benign markers, and preserved structured-data shape.

## What Runs

| Task | Case | Channel | Expected behavior |
| --- | --- | --- | --- |
| Protect model input | `prompt-before-model` | `prompt.input` | Email and API-key shapes are replaced before dispatch |
| Protect tool execution | `tool-call-before-execution` | `tool.call.arguments` | PII is replaced while tool name, case ID, and scalar fields survive |
| Protect agent context | `mcp-resource-before-context` | `mcp.resource.content` | Email and a token-bearing URL are replaced before context assembly |
| Protect long-term state | `memory-before-persistence` | `memory.write` | Email and JWT shapes are replaced before storage or embedding |
| Protect application logs | `log-before-handler` | `log.record` | Email and authorization-header shapes are replaced before handlers |
| Protect telemetry | `trace-before-export` | `trace.span.attributes` | Email is replaced while trace structure and benign attributes survive |

The complete compatibility contract also tests model output, tool results,
credential blocking, private keys, cards, malformed JSON, Unicode, and a
false-positive control. See
[`compatibility/README.md`](../compatibility/README.md).

## Safe Report Fields

Each case emits only:

| Field | Meaning |
| --- | --- |
| `case_id` | Stable synthetic case identifier |
| `boundary` / `channel` | Where redaction was applied |
| `input_sha256` | Hash of the synthetic input, never the input itself |
| `output_sha256` | Hash of placeholder-only output, never the output itself |
| `finding_count` | Findings produced by the public `Veil` API |
| `redacted_count` | Findings replaced before the boundary |
| `leak_count` | Synthetic sensitive markers still present after processing |
| `benign_preserved` | Whether non-sensitive control markers survived |
| `structure_preserved` | Whether dictionaries, lists, and scalar fields kept their shape |
| `gate` / `reasons` | Pass/fail state and raw-value-free failure categories |

The report deliberately excludes raw fixture values, redacted payloads,
placeholder fingerprints, environment variables, personal paths, timestamps,
and network/provider metadata. Fixed replay secrets and scopes are safe only
for these built-in synthetic cases; never reuse them for application data.

## Determinism And Failure Behavior

The built-in input, HMAC secret, scope, and serializer are fixed, so two runs of
the same pyveil version produce the same report. Tests plant an unsupported
synthetic marker and assert that `leak_count` becomes non-zero, the case gate
fails, and the process would return a non-zero exit code.

CI runs the replay directly and separately installs the candidate wheel on the
minimum and maximum supported Python versions. The wheel smoke test changes to
a temporary directory before importing pyveil and running the command, which
prevents the source checkout from hiding missing package files.

## Use The Real Boundary

The replay proves a narrow built-in scenario. Production code still creates its
own secret and scope and applies `Veil` immediately before the real boundary:

```python
from pyveil import Channel, Veil

veil = Veil.high(secret=b"load-this-from-your-secret-store", scope="tenant/session")
safe = veil.redact_data(messages, channel=Channel.PROMPT_INPUT)
response = call_llm(safe.data)
```

Read the [redaction reference](redaction-reference.md), [threat
model](threat-model.md), and [known limitations](known-limitations.md) before
production use. Passing the replay is regression evidence for documented
synthetic shapes; it is not full PII recall, a compliance certification, DLP,
or a prompt-injection defense.
