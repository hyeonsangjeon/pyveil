# pyveil Proof-of-Compatibility Receipt

Privacy-safe evidence for the synthetic protection-surface set. Counts and hashes only; no raw prompt, PII, or secret.

- Generated: `2026-07-24T09:24:52Z`
- pyveil: `0.2.4`
- Commit: `caaed4d91347f5bd5ecf30cc4016070257743875`
- Environment: CPython 3.10.12 on Linux
- Gate: **pass** (16/16 fixtures across 8 surfaces)

## Redaction summary

| Entity type | Redacted count |
| --- | --- |
| `API_KEY` | 2 |
| `AUTH_HEADER` | 1 |
| `CREDIT_CARD` | 2 |
| `EMAIL` | 9 |
| `JWT` | 1 |
| `KV_SECRET` | 1 |
| `PHONE` | 3 |
| `PRIVATE_KEY` | 1 |
| `URL_QUERY_SECRET` | 1 |

## Surfaces

| Channel | Fixture | Category | Gate | Redactions | Output SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `log.record` | `log_record_basic` | basic | pass | AUTH_HEADER=1, EMAIL=1 | `0a42d444ea448c17…` |
| `log.record` | `log_record_broken_json` | broken_json | pass | EMAIL=1 | `2a2d9579261e3f85…` |
| `mcp.resource.content` | `mcp_resource_nested` | nested | pass | EMAIL=1, URL_QUERY_SECRET=1 | `956f4b2a085b7da5…` |
| `mcp.resource.content` | `mcp_resource_unicode` | unicode | pass | EMAIL=1, PHONE=1 | `de6f0c647f5b6b93…` |
| `memory.write` | `memory_write_card` | basic | pass | CREDIT_CARD=1 | `6d95bb6161dcb037…` |
| `memory.write` | `memory_write_jwt` | basic | pass | JWT=1 | `d465c676960fcc83…` |
| `memory.write` | `memory_write_kv_secret` | basic | pass | KV_SECRET=1 | `a200b2a50c7aac7d…` |
| `prompt.input` | `prompt_input_basic` | basic | pass | EMAIL=1, PHONE=1 | `50150487a70ac2d1…` |
| `prompt.input` | `prompt_input_unicode` | unicode | pass | CREDIT_CARD=1, EMAIL=1 | `426950e89bbf35f3…` |
| `prompt.output` | `prompt_output_basic` | basic | pass | API_KEY=1 | `283d46ed4ead27b9…` |
| `tool.call.arguments` | `tool_arguments_fail_closed` | fail_closed | pass | API_KEY=1 | `blocked` |
| `tool.call.arguments` | `tool_arguments_pii_redacted` | basic | pass | EMAIL=1 | `bcc7ba817a54b594…` |
| `tool.call.result` | `tool_result_nested` | nested | pass | EMAIL=1, PHONE=1 | `beb09db7925b3746…` |
| `tool.call.result` | `tool_result_private_key` | basic | pass | PRIVATE_KEY=1 | `f314788bc95cff1a…` |
| `trace.span.attributes` | `trace_span_basic` | basic | pass | EMAIL=1 | `72c35d789877fce9…` |
| `trace.span.attributes` | `trace_span_false_positive` | false_positive | pass | - | `4af979b0512c5717…` |
