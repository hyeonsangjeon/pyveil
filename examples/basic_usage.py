"""Basic pyveil usage."""

from pyveil import Veil

veil = Veil.high(secret=b"example-secret", scope="demo")
result = veil.redact_text(
    "Email alice@example.com and call 010-1234-5678.",
    channel="prompt.input",
)

print(result.text)
print(result.stats.counts_by_type)
