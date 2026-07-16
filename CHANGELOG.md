# Changelog

## 0.2.4 - 2026-07-16

### Added

- Installable OpenAI Responses API and Anthropic Messages API redaction
  templates with env, `.env`, YAML, and keyless dry-run support.
- Offline contract tests that exercise the official provider SDKs through
  local mock HTTP transports without credentials, network requests, or spend.
- A Python 3.9 through 3.14 provider-contract CI matrix while preserving the
  dependency-free Python 3.8 through 3.14 core matrix.

## 0.2.3 - 2026-07-16

Local Ollama boundary release.

### Added

- Installable Ollama chat integration with env, `.env`, and YAML configuration,
  a dry-run boundary, response metrics, and configurable context/keep-alive limits.
- A tested `qwen3.5:4b` local-model recipe sized for a 16GB Apple silicon Mac.

### Changed

- Added an optional `ollama` dependency group while keeping the core package
  dependency-free.
- Expanded the README, Cookbook, web Manual, and agent-facing navigation with
  a complete local-model request path and measured memory/latency trade-offs.

## 0.2.2 - 2026-07-15

Azure OpenAI adoption release.

### Added

- Runnable Azure OpenAI v1 Responses API integration with environment, `.env`,
  and non-secret YAML configuration.
- Dry-run output that proves the raw prompt is redacted before the provider
  SDK call, plus tested `.env` and YAML templates.

### Changed

- Added an optional `azure-openai` dependency group while keeping the core
  package dependency-free.
- Expanded the README, Cookbook, web Manual, Pages entry point, and agent-facing
  navigation with a complete Azure OpenAI request path and observed output.

### Fixed

- Kept the Azure OpenAI Manual anchor visible below the fixed navigation bar on
  desktop and mobile layouts.

## 0.2.1 - 2026-07-11

Evidence and organic-discovery release.

### Added

- Search-intent guides for Python LLM PII redaction, MCP redaction, and choosing
  between pyveil, Presidio/NER, guardrail suites, and enterprise DLP.
- A public 39-case synthetic built-in detector regression corpus, standard-library
  evaluator, rendered methodology page, and CI gate.
- `python -m pyveil` as an alternative CLI entry point.
- Compact E.164 phone-number detection.
- `Token` and `ApiKey` authorization-header scheme detection in free text.
- A Pages-served `llms.txt`, site favicon, richer social metadata, and expanded
  sitemap.
- GitHub Discussions as a support and integration Q&A channel.

### Changed

- Expanded PyPI classifiers, keywords, and project links for guides, evaluation,
  and funding.
- FastAPI example moves redaction work to the default executor for large async
  request payloads.
- Clarified that generated `pyveil.yaml` is a reference/validation schema and is
  not automatically loaded by 0.2.x CLI commands.
- Documented detector evidence and limitations without claiming general-world
  PII recall or compliance.

## 0.2.0 - 2026-07-10

Discovery and production-adoption release.

### Added

- `CustomRule` for trusted application regexes and exact known values such as
  customer names, account IDs, and domain-specific identifiers.
- `pyveil demo` for an immediate synthetic before/after demonstration.
- Explicit `-` stdin support for `pyveil redact` and `pyveil scan`.
- Search-oriented GitHub Pages metadata, canonical links, sitemap, and robots
  policy.

### Changed

- Reworked the README around PII and secret redaction for Python LLM apps and
  AI agents, with before/after proof and provider-neutral integration paths.
- Updated PyPI summary, keywords, homepage, documentation, and security links.
- Expanded documentation for custom rules and choosing between pyveil,
  semantic NER, and enterprise DLP.

### Fixed

- Restored the GitHub Actions quality gate by removing an unused example
  import that caused Ruff to fail while all Python test jobs passed.
- Updated checkout and Python setup actions to their Node 24 releases, removing
  GitHub's Node 20 deprecation annotations.

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
