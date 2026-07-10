# Contributing

Thanks for helping improve pyveil.

## Scope

pyveil is agent-native redaction middleware. Good contributions usually improve
one of these areas:

- high-precision detectors with low false-positive risk
- channel-aware policy behavior
- examples for prompts, tool calls, MCP resources, memory, traces, and logs
- documentation that helps agents and humans integrate pyveil safely
- tests that prove raw sensitive values do not leak by default

Out of scope for the dependency-free core:

- broad semantic name/address detection
- compliance guarantees
- reversible vault/unmasking APIs
- proprietary or domain-specific telecom rules

## Development

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
```

Run the compatibility matrix before release-impacting changes:

```bash
for v in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-venv-$v" uv run --python "$v" --extra test pytest -q --disable-warnings --no-cov
done
```

## Detector Contributions

Detector changes need:

- synthetic positive and negative tests
- a short provenance note in `docs/detector-provenance.md`
- a false-positive rationale
- safety tests proving raw sensitive values do not appear in findings,
  exceptions, or logs by default

## Pull Requests

Keep PRs narrow. Include:

- what changed
- why the change is needed
- tests run
- any compatibility or safety impact
