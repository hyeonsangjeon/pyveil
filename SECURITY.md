# Security Policy

pyveil helps reduce sensitive context exposure, but it does not guarantee removal of all sensitive data and does not provide legal or regulatory compliance by itself.

## Supported Reports

Please report:

- raw sensitive values stored in findings, exceptions, or logs
- detector bypasses for supported high-precision entities
- placeholder collision or scoping issues
- unsafe reversible behavior
- regex denial-of-service cases

## Design Commitments

- No network calls in core detectors.
- No reversible vault or unmasking API.
- No raw findings by default.
- HMAC placeholders use caller-provided secrets and scopes.

## Integration Boundaries

- Redaction wrappers are opt-in. Calling an SDK or agent runtime directly
  bypasses the corresponding pyveil example.
- OpenAI Agents input guardrails are not used as redaction transformers; input
  is redacted before `Runner.run`.
- The LiteLLM Proxy example handles list-valued `messages` only. Other endpoint
  bodies and fields require their own tested boundary.
- pyveil does not erase the original object from application memory. Avoid raw
  logging and tracing before the redaction boundary.
- Provider, proxy, or agent tracing must be configured so it does not capture
  raw input upstream of pyveil.

See the [OpenAI Agents SDK vs LiteLLM comparison](docs/integrations/openai-agents-vs-litellm.md)
for the exact inputs, outputs, bypass risks, and current limits.
