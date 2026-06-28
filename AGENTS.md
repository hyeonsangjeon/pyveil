# AGENTS.md

## Project Purpose

pyveil is agent-native redaction middleware. Keep it focused on redacting sensitive context before prompts, tool calls, MCP resources, memory, logs, and traces cross trust boundaries.

Do not turn pyveil into a general DLP suite, gateway, Presidio clone, or prompt-injection firewall.

## Setup

- Install local package: `python3 -m pip install -e .`
- Run tests: `python3 -m pytest`
- Run lint: `uv run --extra dev ruff check .`
- Run typecheck: `uv run --extra dev mypy pyveil tests`
- Build package: `uv run --with build python -m build`
- Check package: `uv run --with twine python -m twine check dist/*`
- Run CLI locally: `PYVEIL_SECRET=dev-secret python3 -m pyveil.cli redact <file>`

## Architecture

The core pipeline is:

```text
detector -> finding -> policy -> masker
```

- Detectors find high-precision sensitive values.
- Findings never include raw sensitive values by default.
- Policy decides per channel whether to redact or block.
- Maskers produce LOW shape-preserving output or HIGH HMAC placeholders.
- Prefer public `Channel` and `Entity` enums in examples when avoiding stringly-typed policy code.

## Security Rules

- Never log raw sensitive values in tests, exceptions, docs, or fixtures.
- Do not expose reversible unmasking to an LLM-controlled tool.
- Do not port proprietary legacy rules or business-specific telecom rules.
- Do not add CLI defaults that silently reuse a hard-coded redaction secret.
- Keep CLI JSON input structure-preserving; tool, MCP, and trace payloads are usually JSON-shaped.
- Keep core deterministic, local, and standard-library only for v0.1.
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
- [docs/integrations/mcp.md](docs/integrations/mcp.md)
- [docs/integrations/logging.md](docs/integrations/logging.md)
- [docs/integrations/tracing.md](docs/integrations/tracing.md)

Examples:

- [examples/basic_usage.py](examples/basic_usage.py)
- [examples/redact_json.py](examples/redact_json.py)
- [examples/log_filter.py](examples/log_filter.py)
- [examples/mcp_tool_result.py](examples/mcp_tool_result.py)
- [examples/mcp_server_wrapper.py](examples/mcp_server_wrapper.py)
- [examples/memory_write.py](examples/memory_write.py)
- [examples/openai_agents_guardrail.py](examples/openai_agents_guardrail.py)
- [examples/fastapi_middleware.py](examples/fastapi_middleware.py)
- [examples/litellm_proxy_filter.py](examples/litellm_proxy_filter.py)

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
```

Full local release check:

```bash
for v in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-venv-$v" uv run --python "$v" --extra test pytest -q --disable-warnings --no-cov
done

uv run --extra dev python -m build
uv run --extra dev python -m twine check dist/*
```
