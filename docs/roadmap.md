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

- Config loading into `Policy` and `Veil` objects.
- Optional framework adapters where they do not add hard runtime dependencies.
- Richer stats for blocked/redacted/passed findings.

## Non-goals

- Broad semantic PII detection in dependency-free core.
- Reversible vault or unmasking API.
- Compliance certification.
- Prompt-injection firewall behavior.
