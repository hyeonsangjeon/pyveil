# Changelog

## 0.1.2 - 2026-06-28

Documentation and adoption polish.

### Added

- PyPI package link in the README body so the PyPI long description and GitHub
  README stay aligned.
- Practical integration examples for agent context wrapping, FastAPI middleware,
  LiteLLM-style proxy filtering, and MCP-style server result wrapping.
- `CONTRIBUTING.md`, issue templates, PR template, FAQ, and roadmap.

### Changed

- README usage guide links now target the `v0.1.2` release assets.

### Fixed

- Email detection now handles addresses followed by sentence punctuation such
  as `alice@example.com.`.

## 0.1.1 - 2026-06-27

Initial agent-native redaction release.

This version supersedes the legacy `0.1.0` PyPI package metadata and starts the
agent-native package line.

### Added

- `Veil.high()` and `Veil.low()` facade constructors.
- `redact_text()` and `redact_data()` APIs.
- HMAC stable placeholders for `HIGH` redaction.
- Legacy-style shape-preserving `LOW` redaction.
- Channel-aware policy for prompts, tool calls, MCP resources, memory, traces, and logs.
- High-precision v0.1 detectors for email, phone, card, JWT, auth headers, private keys, API keys, URL query secrets, and key-value secrets.
- CLI commands: `redact`, `scan`, `init`, and `test-config`.
- Logging and MCP helper integrations.
- Agent-facing docs: `AGENTS.md`, `llms.txt`, threat model, known limitations, and detector provenance.
- Public `Channel` and `Entity` enums for policy examples and agent-readable code.
- `max_input_chars` guard for plain text and structured data redaction.

### Changed

- CLI JSON input is treated as structured data; `pyveil redact` requires `--format json` for JSON-shaped input.
- CLI placeholders can be scoped with `--scope` or `PYVEIL_SCOPE`.
- Structured sensitive-key redaction preserves non-string scalar types instead of replacing booleans, numbers, and nulls with strings.
