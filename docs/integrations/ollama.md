# Ollama Integration

Use `pyveil.integrations.ollama` when a prompt should be redacted immediately
before it enters a local Ollama model.

```text
raw prompt -> pyveil HIGH redaction -> Ollama Client.chat -> local model
```

## Install

Install the optional official client and configuration dependencies, then pull
a model:

```bash
pip install "pyveil[ollama]"
ollama pull qwen3.5:4b
```

The integration does not pull a model automatically. Model downloads are large
and should remain an explicit operator decision.

## Why `qwen3.5:4b` For A 16GB Mac

The development machine used for this integration is an M1 Mac mini with 16GB
of unified memory. The selected `qwen3.5:4b` tag is a Q4_K_M model with about
4.7B parameters and a 3.4GB download. The integration limits context to 4096
tokens even though the model supports more, because KV cache grows with context.

Observed locally with Ollama 0.31.2:

| Check | Observed result |
| --- | --- |
| Loaded model size from `ollama ps` | 3.2GB |
| Processor | 100% GPU |
| Context | 4096 tokens |
| Cold live request | 8.1s total, 5.2s model load |
| Warm live request | 1.3s total, 0.25s load |
| Memory free indicator while resident | 26% |
| Memory free indicator after unload | 57% |

These values are a single-machine smoke test, not a benchmark. Background
applications, prompt length, model updates, and Ollama versions will change
them.

## Dry Run

Dry-run proves what would cross the client boundary without loading the model:

```bash
PYVEIL_SECRET=docs-demo-secret \
  python -m pyveil.integrations.ollama --dry-run
```

```text
mode: dry-run
model: qwen3.5:4b
host: http://127.0.0.1:11434
sent-to-ollama: Write a one-sentence support follow-up for [EMAIL:71c6727a7fa2] or [PHONE:b4b889df07ce].
findings: EMAIL=1, PHONE=1
ollama-response: skipped (--dry-run)
```

## Live Call

```bash
export PYVEIL_SECRET="a-long-random-hmac-secret"
python -m pyveil.integrations.ollama
```

Or call the reusable API:

```python
from pyveil.integrations.ollama import ask_ollama, load_settings

settings = load_settings()
result = ask_ollama(
    "Write a support reply for alice@example.com or 010-1234-5678.",
    settings,
)

print(result.redacted_input)
print(result.output_text)
print(result.total_duration_ms, result.prompt_eval_count, result.eval_count)
```

`redacted_input` is the exact value passed to `Client.chat`. Findings and
exceptions do not retain the original email or phone number.

## Configuration

Priority is process environment, `.env`, YAML, then defaults.

| Environment | YAML key | Default | Purpose |
| --- | --- | --- | --- |
| `OLLAMA_HOST` | `ollama.host` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `ollama.model` | `qwen3.5:4b` | Local model tag |
| `OLLAMA_NUM_CTX` | `ollama.num_ctx` | `4096` | Context and KV-cache limit |
| `OLLAMA_NUM_PREDICT` | `ollama.num_predict` | `128` | Maximum output tokens |
| `OLLAMA_TEMPERATURE` | `ollama.temperature` | `0.2` | Sampling temperature |
| `OLLAMA_KEEP_ALIVE` | `ollama.keep_alive` | `0` | How long the model stays resident |
| `OLLAMA_TIMEOUT` | `ollama.timeout_seconds` | `120` | HTTP timeout in seconds |
| `PYVEIL_SECRET` | `pyveil.secret_env` | required | HMAC secret environment variable |
| `PYVEIL_SCOPE` | `pyveil.scope` | `ollama/example` | Placeholder namespace |

```bash
python -m pyveil.integrations.ollama \
  --config examples/ollama.example.yaml \
  --env-file .env
```

The pyveil secret cannot be stored directly in YAML. The loader rejects a
`pyveil.secret` field; YAML may only name the environment variable that holds
it.

## Memory And Latency

- Keep the default `OLLAMA_KEEP_ALIVE=0` for one-shot jobs or a memory-busy
  16GB machine. Ollama unloads the model after the response.
- Set `OLLAMA_KEEP_ALIVE=5m` for repeated agent turns. Warm requests are much
  faster, but the model remains resident during that window.
- Keep `OLLAMA_NUM_CTX=4096` unless the application proves it needs more.
- Inspect current residency with `ollama ps`; unload manually with
  `ollama stop qwen3.5:4b`.

## Boundary Notes

- `127.0.0.1` keeps the redacted request on the machine. A remote
  `OLLAMA_HOST` creates a network boundary even though the raw PII was removed.
- pyveil protects the input boundary. If model output will be logged, stored,
  or sent onward, redact it again with channel `prompt.output`.
- Regex and known-value rules do not discover arbitrary names or addresses.
- The integration disables thinking output and returns only
  `message.content`; it does not persist or expose a reasoning trace.
