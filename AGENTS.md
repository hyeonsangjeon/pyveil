# AGENTS.md

## Project Purpose

pyveil is local PII and secret redaction middleware for Python LLM apps and AI
agents. Keep it focused on redacting sensitive context before prompts, tool
calls, MCP resources, memory, logs, and traces cross trust boundaries.

Do not turn pyveil into a general DLP suite, gateway, Presidio clone, or prompt-injection firewall.

## Setup

- Install local package: `python3 -m pip install -e .`
- Run tests: `python3 -m pytest`
- Run lint: `uv run --extra dev ruff check .`
- Run typecheck: `uv run --extra dev mypy pyveil tests`
- Build package: `uv run --with build python -m build`
- Check package: `uv run --with twine python -m twine check dist/*`
- Run CLI demo: `python3 -m pyveil demo`
- Run CLI locally: `PYVEIL_SECRET=dev-secret python3 -m pyveil redact <file>`
- Run detector evaluation: `python3 evaluation/evaluate.py --check`
- Run the OpenAI boundary without a key: `PYVEIL_SECRET=dev-secret OPENAI_MODEL=gpt-5.6-luna python3 -m pyveil.integrations.openai --dry-run`
- Run the Anthropic boundary without a key: `PYVEIL_SECRET=dev-secret ANTHROPIC_MODEL=claude-haiku-4-5 python3 -m pyveil.integrations.anthropic --dry-run`
- Run the Ollama boundary without a model call: `PYVEIL_SECRET=dev-secret python3 -m pyveil.integrations.ollama --dry-run`
- Run offline provider SDK contracts: `uv run --extra openai --extra anthropic --extra test pytest tests/test_provider_contracts.py -m provider_contract --no-cov`

## Architecture

The core pipeline is:

```text
detector -> finding -> policy -> masker
```

- Detectors find high-precision sensitive values.
- Findings never include raw sensitive values by default.
- Policy decides per channel whether to redact or block.
- Maskers produce LOW shape-preserving output or HIGH HMAC placeholders.
- `CustomRule` adds trusted regex or exact known-value findings to the same
  detector, finding, policy, and masker pipeline.
- Prefer public `Channel` and `Entity` enums in examples when avoiding stringly-typed policy code.

## Security Rules

- Never log raw sensitive values in tests, exceptions, docs, or fixtures.
- Do not expose reversible unmasking to an LLM-controlled tool.
- Do not port proprietary legacy rules or business-specific telecom rules.
- Do not add CLI defaults that silently reuse a hard-coded redaction secret.
- Keep CLI JSON input structure-preserving; tool, MCP, and trace payloads are usually JSON-shaped.
- Keep core deterministic, local, and standard-library only.
- Treat custom regexes as trusted application code. Require focused positive
  and negative tests and keep `max_input_chars` enabled.
- New detectors must include synthetic positive and negative tests.
- Prefer high precision over broad but noisy detection.

Do not present pyveil as:

- A compliance guarantee
- A secret-scanning replacement
- A prompt-injection firewall
- A reversible token vault

## Agent Adoption

This repository includes files meant for coding agents and LLM readers:

- [AGENTS.md](AGENTS.md) for agent instructions
- [llms.txt](llms.txt) for LLM-friendly navigation
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/threat-model.md](docs/threat-model.md)
- [docs/faq.md](docs/faq.md)
- [docs/known-limitations.md](docs/known-limitations.md)
- [docs/detector-provenance.md](docs/detector-provenance.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/release-checklist.md](docs/release-checklist.md)
- [docs/evaluation.html](docs/evaluation.html)
- [docs/guides/](docs/guides/)
- [docs/integrations/mcp.md](docs/integrations/mcp.md)
- [docs/integrations/openai.md](docs/integrations/openai.md)
- [docs/integrations/anthropic.md](docs/integrations/anthropic.md)
- [docs/integrations/ollama.md](docs/integrations/ollama.md)
- [docs/integrations/logging.md](docs/integrations/logging.md)
- [docs/integrations/tracing.md](docs/integrations/tracing.md)

Examples:

- [examples/basic_usage.py](examples/basic_usage.py)
- [examples/custom_rules.py](examples/custom_rules.py)
- [examples/redact_json.py](examples/redact_json.py)
- [examples/log_filter.py](examples/log_filter.py)
- [examples/mcp_tool_result.py](examples/mcp_tool_result.py)
- [examples/mcp_server_wrapper.py](examples/mcp_server_wrapper.py)
- [examples/memory_write.py](examples/memory_write.py)
- [examples/openai_agents_guardrail.py](examples/openai_agents_guardrail.py)
- [examples/fastapi_middleware.py](examples/fastapi_middleware.py)
- [examples/litellm_proxy_filter.py](examples/litellm_proxy_filter.py)
- [examples/azure_openai.py](examples/azure_openai.py)
- [examples/openai.py](examples/openai.py)
- [examples/anthropic.py](examples/anthropic.py)
- [examples/ollama.py](examples/ollama.py)

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
uv run --extra openai --extra anthropic --extra test \
  pytest tests/test_provider_contracts.py -m provider_contract --no-cov
```

The dependency-free core is tested on Python 3.8 through 3.14. The current
official OpenAI and Anthropic SDKs require Python 3.9+, so their serialization
contract matrix covers Python 3.9 through 3.14. Their keyless dry-runs remain
usable on Python 3.8 because provider SDK imports happen only for live calls.

Full local release check:

```bash
for v in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-venv-$v" uv run --python "$v" --extra test pytest -q --disable-warnings --no-cov
done

for v in 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-provider-$v" uv run --python "$v" \
    --extra openai --extra anthropic --extra test \
    pytest tests/test_provider_contracts.py -m provider_contract -q --no-cov
done

uv run --extra dev python -m build
uv run --extra dev python -m twine check dist/*
```
