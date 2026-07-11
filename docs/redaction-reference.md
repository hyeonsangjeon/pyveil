# Redaction Reference

This page is the quick board for what pyveil detects and how each finding is masked.

Use this as the operator/manual view. For detector provenance and contribution rules, see [detector-provenance.md](detector-provenance.md).

## Levels

| Level | Intended use | Behavior |
| --- | --- | --- |
| `HIGH` | Agent, model, tool, MCP, memory, trace, and external log boundaries | Replaces each sensitive value with a deterministic HMAC placeholder such as `[EMAIL:c2c2a4d06bfa]` |
| `LOW` | Human-facing diagnostics and legacy-style previews | Keeps limited shape for email, phone, and card values; credential-like values become `[TYPE]` |

`HIGH` is the default recommendation for AI agent context. Placeholders are stable for the same `secret`, `scope`, entity type, and source value. Changing `scope` changes the placeholder and reduces cross-context linkability.

## Masking Board

Examples below use synthetic values with `secret=b"docs-secret"` and `scope="docs/reference"`. The exact 12 hex characters will differ when callers use different secrets or scopes.

| Target | Example input | `HIGH` output | `LOW` output |
| --- | --- | --- | --- |
| Email address | `alice@example.com` | `[EMAIL:c2c2a4d06bfa]` | `al***@e******.com` |
| Korean mobile phone | `010-1234-5678` | `[PHONE:3b2b3e0e6c51]` | `010-****-5678` |
| International-ish phone | `+1 415 555 0199` | `[PHONE:018e583b4e44]` | `+1 415 *** 0199` |
| Credit card, Luhn-valid | `4242 4242 4242 4242` | `[CREDIT_CARD:630b6f1dd4d6]` | `**** **** **** 4242` |
| JWT | `eyJ...`.`eyJ...`.`signature...` | `[JWT:5435e2049349]` | `[JWT]` |
| Bearer or Basic authorization header | `Authorization: Bearer synthetic-token-value` | `[AUTH_HEADER:29beafd29bb3]` | `[AUTH_HEADER]` |
| Private key block | `-----BEGIN PRIVATE KEY-----...` | `[PRIVATE_KEY:749fe49ede10]` | `[PRIVATE_KEY]` |
| API key with high-signal prefix | `sk-proj-abcdefghijklmnopqrstuvwxyz123456` | `[API_KEY:0f8d254df046]` | `[API_KEY]` |
| URL query secret value | `?access_token=synthetic-token&state=ok` | `?access_token=[URL_QUERY_SECRET:3e173d9240a2]&state=ok` | `?access_token=[URL_QUERY_SECRET]&state=ok` |
| Key-value secret value | `password=synthetic-password` | `password=[KV_SECRET:ce3accc557cf]` | `password=[KV_SECRET]` |

## Supported Entity Types

| Entity | Detector behavior |
| --- | --- |
| `EMAIL` | High-precision email regex for common address shapes |
| `PHONE` | Korean mobile/local, separated international, and compact E.164 phone patterns |
| `CREDIT_CARD` | Numeric card candidates that pass Luhn validation |
| `JWT` | Compact JWT-like tokens beginning with the common encoded JSON header shape |
| `AUTH_HEADER` | `Authorization: Bearer ...` and `Authorization: Basic ...` header values |
| `PRIVATE_KEY` | PEM-style private key blocks |
| `API_KEY` | High-signal provider prefixes such as OpenAI, GitHub, Slack, Google API key, and AWS access key shapes |
| `URL_QUERY_SECRET` | Sensitive URL query parameter values such as `access_token`, `refresh_token`, `api_key`, `secret`, and `auth` |
| `KV_SECRET` | Text or structured values under sensitive keys such as `password`, `secret`, `token`, `cookie`, and related names |
| Custom entity | Exact values or trusted application regexes supplied through `CustomRule` |

Free-text authorization headers recognize the common `Bearer`, `Basic`, `Token`,
and `ApiKey` schemes. Phone detection includes compact E.164 shapes, but it is
not a country-aware phone-number parser.

## Custom Rules

Use an exact rule when authenticated application data already tells you which
names or values are sensitive:

```python
from pyveil import CustomRule, Veil

rules = [
    CustomRule.exact("PERSON", ["Alice Kim", "Hong Gildong"]),
    CustomRule("CUSTOMER_ID", r"\bCUS-[A-Z0-9]{8}\b", rule_id="customer_id"),
]

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session", rules=rules)
safe = veil.redact_text("Alice Kim owns CUS-A1B2C3D4.")
```

Exact rules escape source values, prefer longer matches, and use word
boundaries by default. Set `ignore_case=True` only when case is not meaningful.
Custom regexes are trusted code and run inside the same `max_input_chars`
boundary as built-in detectors.

## Channel Policy

The default policy redacts supported findings on most channels.

Credential-like values are blocked by default in `tool.call.arguments` because model-controlled tool arguments should not carry raw credentials:

| Channel | Blocked by default |
| --- | --- |
| `tool.call.arguments` | `AUTH_HEADER`, `PRIVATE_KEY`, `API_KEY`, `JWT`, `KV_SECRET`, `URL_QUERY_SECRET` |

When blocked data is found, pyveil raises `BlockedSensitiveData`. The exception reports counts by entity type and does not include raw sensitive values.

## Structured Data

Use `redact_data` for dicts, lists, JSON strings, tool arguments, MCP payloads, trace attributes, and memory records.

```python
from pyveil import Veil

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session")

safe = veil.redact_data(
    {
        "email": "alice@example.com",
        "headers": {"Authorization": "Bearer synthetic-token-value"},
        "metadata": {"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456"},
    },
    channel="tool.call.result",
)

print(safe.data)
```

Structured payloads keep their shape. If a key name is sensitive, pyveil treats the value as sensitive even when the value itself does not match a provider-specific token pattern.

## What Is Not Included

Core intentionally does not try to broadly detect:

- personal names
- postal addresses
- company-specific account, billing, telecom, membership, or device identifiers
- arbitrary domain-specific IDs unless supplied with `CustomRule`
- every provider token format

Add known values and narrow domain IDs with `CustomRule`. Use upstream semantic
NER when the application must discover unknown names, organizations, locations,
or addresses.
