# Detector Provenance

pyveil uses a clean-room detector set. The legacy Java masking files in
`local.data/` are private reference material and are not copied into the package.

## Rules

- Use synthetic examples only.
- Prefer high precision over broad detection.
- Do not port proprietary telecom, billing, membership, device, or business-rule identifiers.
- Keep core detectors local and deterministic.
- Do not add network calls to core detection.
- Do not store raw findings by default.

## Built-in Detectors

| Detector | Entity | Provenance | Notes |
| --- | --- | --- | --- |
| `email` | `EMAIL` | Custom regex, synthetic tests | Shape-preserving LOW mask, HMAC HIGH placeholder |
| `phone` | `PHONE` | Custom regex, synthetic Korean, separated international, and compact E.164 tests | Not a complete phone-number parser |
| `credit_card` | `CREDIT_CARD` | Custom regex plus Luhn validation | Synthetic test numbers only |
| `jwt` | `JWT` | Structural compact JWT detector | Blocked by default in `tool.call.arguments` |
| `auth_header` | `AUTH_HEADER` | Authorization header regex for Bearer, Basic, Token, and ApiKey schemes | Blocked by default in `tool.call.arguments` |
| `private_key` | `PRIVATE_KEY` | PEM block pattern | Blocked by default in `tool.call.arguments` |
| `api_key` | `API_KEY` | High-signal provider prefixes | Blocked by default in `tool.call.arguments` |
| `url_query_secret` | `URL_QUERY_SECRET` | Sensitive query parameter names | Blocked by default in `tool.call.arguments` |
| `kv_secret` | `KV_SECRET` | Sensitive key-name patterns | Blocked by default in `tool.call.arguments` |

## Adding A Detector

New detectors must include:

- a synthetic positive test
- a synthetic negative test
- a short provenance note in this file
- no proprietary source material
- no raw sensitive values in findings, exceptions, logs, or fixtures
