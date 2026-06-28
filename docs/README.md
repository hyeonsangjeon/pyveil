# pyveil Documentation

pyveil redacts secrets before your AI agent sees them. It is agent-native redaction middleware for AI context boundaries.

Start with:

- [Threat model](threat-model.md)
- [FAQ](faq.md)
- [Known limitations](known-limitations.md)
- [Detector provenance](detector-provenance.md)
- [Roadmap](roadmap.md)
- [Release checklist](release-checklist.md)
- [MCP integration](integrations/mcp.md)
- [Logging integration](integrations/logging.md)
- [Tracing integration](integrations/tracing.md)

The stable v0.1 shape is:

```text
detector -> finding -> policy -> masker
```

Channels such as `prompt.input`, `tool.call.arguments`, `mcp.resource.content`, `memory.write`, `trace.span.attributes`, and `log.record` are part of the public model. Python callers can use the public `Channel` enum instead of raw strings.
