# pyveil Documentation

pyveil provides local PII and secret redaction for Python LLM applications and
AI agents. It runs before prompts, tool calls, MCP resources, memory, logs, and
traces cross application boundaries.

Start with:

- [Rendered guide hub](https://hyeonsangjeon.github.io/pyveil/guides/)
- [Reproducible evaluation](https://hyeonsangjeon.github.io/pyveil/evaluation.html)
- [LLM-readable navigation](https://hyeonsangjeon.github.io/pyveil/llms.txt)
- [Threat model](threat-model.md)
- [FAQ](faq.md)
- [Cookbook](cookbook.md)
- [Ollama local-model integration](integrations/ollama.md)
- [Azure OpenAI env/YAML integration](../pyveil/integrations/azure_openai.py)
- [Redaction reference](redaction-reference.md)
- [Known limitations](known-limitations.md)
- [Detector provenance](detector-provenance.md)
- [Roadmap](roadmap.md)
- [Release checklist](release-checklist.md)
- [MCP integration](integrations/mcp.md)
- [Logging integration](integrations/logging.md)
- [Tracing integration](integrations/tracing.md)

The stable core shape is:

```text
detector -> finding -> policy -> masker
```

Channels such as `prompt.input`, `tool.call.arguments`, `mcp.resource.content`, `memory.write`, `trace.span.attributes`, and `log.record` are part of the public model. Python callers can use the public `Channel` enum instead of raw strings.

Applications can add known sensitive values and narrow domain identifiers with
the public `CustomRule` API while keeping semantic NER out of the dependency-free
core.

`index.html`, `manual.html`, `evaluation.html`, and `guides/` are static GitHub
Pages content. Serve GitHub Pages from the repository `/docs` directory to
publish them.
