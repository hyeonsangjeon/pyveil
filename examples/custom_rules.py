"""Redact known names and application-specific identifiers without NER."""

from pyveil import CustomRule, Veil

rules = [
    CustomRule.exact("PERSON", ["Alice Kim", "Hong Gildong"]),
    CustomRule("CUSTOMER_ID", r"\bCUS-[A-Z0-9]{8}\b", rule_id="customer_id"),
]

veil = Veil.high(secret=b"example-secret", scope="tenant/session", rules=rules)
result = veil.redact_text(
    "Alice Kim owns CUS-A1B2C3D4. Email alice@example.com.",
    channel="prompt.input",
)

print(result.text)
# [PERSON:...] owns [CUSTOMER_ID:...]. Email [EMAIL:...].
