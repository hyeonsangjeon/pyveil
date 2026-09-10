# Roadmap

This roadmap is directional, not a compatibility promise.

## 0.1.x

- Keep core dependency-free and Python 3.8 through 3.14 compatible.
- Improve integration examples for agents, MCP, logging, tracing, and gateways.
- Tighten documentation around safety boundaries and known limitations.
- Keep detector changes conservative and high precision.

## 0.2.x

- Stabilize the `CustomRule` API for exact known values and domain identifiers.
- Improve CLI and provider-neutral adoption paths without adding core
  dependencies.
- Maintain and expand the reproducible synthetic detector evaluation corpus.
- Publish machine-dependent latency diagnostics without presenting them as an
  SLA.

## Future Candidates

- Provider orchestration and custom rules in file-run configuration, if needed.
- Optional framework adapters where they do not add hard runtime dependencies.
- Richer stats for blocked/redacted/passed findings.

## 0.3.x

- Keep the file-run configuration executable, strict, and dependency-free.
- Maintain clean-install timing and byte-reproducibility checks.
- Keep synthetic regression tours separate from real user-file processing.

## Non-goals

- Broad semantic PII detection in dependency-free core.
- Reversible vault or unmasking API.
- Compliance certification.
- Prompt-injection firewall behavior.
