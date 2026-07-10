# Known Limitations

pyveil is intentionally narrow.

## Not Guaranteed

- It does not find every sensitive value.
- It does not prove GDPR, HIPAA, PCI, or other compliance.
- It does not prevent prompt injection.
- It does not replace access control, secret scanning, DLP, or provider-side safety controls.

## Detector Limits

- Broad semantic name and address discovery is not enabled in core. Use
  `CustomRule.exact(...)` only when the application already knows the values,
  or layer a dedicated NER system upstream.
- Phone detection favors common Korean and international-ish patterns.
- API key detection covers high-signal prefixes and key names, not every provider.
- Structured redaction follows dict/list/JSON payloads but cannot infer every domain-specific identifier.

## Placeholder Limits

Stable placeholders preserve referential consistency, but that also creates linkability. Use separate `scope` values for tenants, sessions, or runs when cross-context linkage is not desired.

## Runtime Limits

- Core enforces `max_input_chars` before detection for plain text and structured string content.
- Core does not enforce per-regex timeouts because it stays standard-library only. Custom regexes are trusted application code; keep them narrow and retain size limits and upstream request timeouts around untrusted large inputs.
