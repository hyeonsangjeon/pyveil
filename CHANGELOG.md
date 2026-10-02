# Changelog

## 0.3.1 - 2026-10-02

Documentation and onboarding patch. No changes to the core redaction API or
detector behavior.

### Documentation and maintainer tooling

- Put a runnable, keyless Python example before configuration details; align
  README, homepage, and manual and make README file links usable on PyPI.
- Clarify installed modules versus checkout-only OpenAI Agents / LiteLLM
  recipes, with complete environment setup and direct integration links.
- Verify the exact quickstart and keyless recipes against clean installed
  wheels; check public quickstart drift and local documentation navigation.
- Add an opt-in maintainer traffic snapshot script with private local output,
  actual returned windows, and explicit limits on usage/conversion inference.

### Upgrading

- Install with `python -m pip install --upgrade pyveil==0.3.1`.
- Existing file-run configurations pin an exact version. After reviewing this
  release, change `pyveil_version` in your `pyveil.json` to `0.3.1`, or keep
  `0.3.0` installed for a pinned reproduction. Keep your input, scope, and
  private key unchanged; do not re-run `init` or regenerate keys to upgrade.

## 0.3.0 - 2026-09-11

### Executable file runs

- Added `pyveil run [pyveil.json]`: the installed redactor reads a real input
  file, applies the configured channel/level/actions, and writes redacted data
  plus a receipt to a new private run directory.
- Added strict, dependency-free JSON configuration with an exact package-version
  pin, config-relative paths, explicit input format/origin, size limit, and one
  secret reference. There are no hidden scope or policy environment overrides.
- `init` creates a random per-directory private key unless `--secret-env` is
  chosen. `--example` creates a labeled synthetic input file, not a mock response.
  Existing files and keys are never overwritten.
- Receipts distinguish actual local processing from input provenance and record
  the config/output hashes, keyed input digest, action counts, and measured time.
- Installed-wheel CI now creates a fresh environment, processes the file twice,
  verifies identical outputs and failure paths, and fails after 300 seconds.

### Migration

- `init` and `test-config` now use executable `pyveil.json`. The old root
  `pyveil.yaml` was only a reference and was never loaded by the core CLI.
  YAML reference files are now rejected rather than falsely validated.
- Existing `redact`, `scan`, Python APIs, and provider-specific YAML loaders
  retain their interfaces. See `docs/file-runs.md` for migration and error codes.
- Missing secrets are reported before waiting for stdin. File/encoding/size
  failures have explicit CLI errors rather than tracebacks.

### Added

- `pyveil replay` and `examples/privacy_replay.py` for a deterministic, keyless
  Privacy Boundary Replay across prompt, tool-call, MCP, memory, log, and trace
  boundaries.
- Raw-value-free replay evidence with input/output hashes, finding and redaction
  counts, leak counts, benign-marker preservation, structure preservation, and
  a gate-based process exit code.
- Minimum/maximum Python clean-wheel smoke tests that run the replay outside the
  source checkout.
- A resume-safety pass in `pyveil replay` that re-crosses every boundary with
  already-redacted state, proving no synthetic marker returns on resume and
  reporting whether re-redaction is a byte-stable fixed point.

### Changed

- Added a task-first replay board and direct evidence path near the top of the
  README, plus a detailed replay guide for report semantics and limitations.

## 0.2.5 - 2026-07-24

### Added

- Keyless contract tests for the OpenAI Agents pre-dispatch wrapper and the
  LiteLLM SDK and Proxy redaction boundaries.
- A machine-readable compatibility manifest and 16 synthetic per-channel
  fixtures covering every protection surface, with a validator that fails on
  manifest or documentation drift.
- A privacy-safe Proof-of-Compatibility Receipt (redaction counts and output
  hashes only) and a reproducible zero-runtime-dependency check, both wired
  into CI.

### Changed

- Added an integration-first README and Cookbook index for visitors arriving
  through OpenAI Agents, LiteLLM, provider SDK, MCP, logging, and memory paths.
- Added a side-by-side OpenAI Agents and LiteLLM comparison covering detection
  location, inputs, provider-bound outputs, bypass risks, and unsupported paths.
- Replaced the abstract OpenAI Agents and LiteLLM snippets with runnable
  examples that redact immediately before the actual SDK or Proxy boundary.
- Hardened CI by pinning GitHub Actions to verified commit SHAs, applying
  least-privilege permissions and concurrency, and adding Dependabot to keep
  the pinned actions current.

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
