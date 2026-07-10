# FAQ

## Is pyveil a DLP product?

No. pyveil is lightweight redaction middleware for agent context boundaries. It
does not replace enterprise DLP, access control, secret scanning, or provider
side safety controls.

## Does pyveil guarantee compliance?

No. It can reduce sensitive-context exposure, but it does not prove GDPR,
HIPAA, PCI, or any other compliance regime.

## Why are placeholders stable?

Stable HMAC placeholders let an agent preserve references across a run without
seeing the raw value. Use different `scope` values when cross-context linkability
is not desired.

## Why not detect names and addresses by default?

Broad semantic detection has higher false-positive and false-negative risk than
the high-precision core detectors. Use `CustomRule.exact(...)` for values the
application already knows, a narrow `CustomRule` regex for domain identifiers,
or a dedicated NER layer for unknown semantic entities.

## Can I unmask values later?

No. pyveil has no reversible vault and no unmasking API. This is intentional: the
default design avoids storing raw sensitive values.

## Does pyveil call external services?

No. Core pyveil uses the Python standard library and does not make network
calls.
