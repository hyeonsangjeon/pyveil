# Threat Model

pyveil sits before context crosses into an AI boundary.

## Assets

- user PII
- credentials and API keys
- auth headers and cookies
- MCP resource contents
- tool call arguments and results
- agent memory writes
- logs, traces, and error reports
- placeholder secrets and scopes

## Boundaries

Redact before:

- sending prompts to an LLM provider
- sending model-generated tool arguments to external systems
- returning tool results to a model
- exposing MCP resources as model context
- writing long-term memory or embeddings
- exporting logs and traces

## Main Risks

- Under-redaction: regexes miss formats, nested payloads, Unicode tricks, or domain-specific identifiers.
- Over-redaction: aggressive masking breaks debugging, search, schemas, and agent reasoning.
- Prompt injection: malicious content can ask a model to reveal raw context. pyveil must run outside the model.
- Stable placeholder linkability: global deterministic placeholders can connect users across tenants or sessions.
- Trace leakage: GenAI traces may contain prompts, tool args, and tool results.
- Memory contamination: raw sensitive values are hard to remove after embedding or memory writes.
- False confidence: redaction is a risk reducer, not a compliance guarantee.

## Mitigations

- Use channel-specific policy.
- Use HMAC placeholders with per-tenant or per-session scope.
- Block credential-like data in model-controlled tool arguments.
- Keep findings raw-free by default.
- Redact before logs, traces, memory, and MCP exposure.
- Publish known limitations instead of overclaiming.
