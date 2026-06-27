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
- No reversible vault in v0.1.
- No raw findings by default.
- HMAC placeholders use caller-provided secrets and scopes.
