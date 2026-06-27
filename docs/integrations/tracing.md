# Tracing Integration

Agent traces may include prompts, system prompts, tool arguments, tool results, metadata, and errors. Redact before exporting trace payloads.

## Minimal Pattern

```python
from pyveil import Veil

veil = Veil.high(secret=b"trace-secret", scope="tenant/session")

def redact_span_attributes(attributes: dict) -> dict:
    return veil.redact_data(attributes, channel="trace.span.attributes").data
```

## OpenTelemetry-Style Hook

```python
safe_attributes = veil.redact_data(
    span_attributes,
    channel="trace.span.attributes",
).data
```

## Langfuse-Style Hook

```python
def mask_trace_payload(payload):
    return veil.redact_data(payload, channel="trace.span.attributes").data
```

## Notes

- Prefer disabling prompt/tool content capture when it is not needed.
- If content capture is enabled, scrub before export.
- Do not store reversible mappings inside trace systems.
