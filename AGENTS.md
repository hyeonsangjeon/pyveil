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
