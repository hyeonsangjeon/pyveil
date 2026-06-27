"""Redact a structured tool payload."""

from pyveil import Veil

payload = {
    "user": "alice@example.com",
    "args": {"phone": "+82 10-1234-5678"},
    "metadata": {"password": "synthetic-secret"},
}

veil = Veil.high(secret=b"example-secret", scope="tool-demo")
print(veil.redact_data(payload, channel="tool.call.result").data)
