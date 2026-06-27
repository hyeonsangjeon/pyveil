"""Redact before writing long-term memory or embeddings."""

from pyveil import Veil

raw_note = "Alice can be reached at alice@example.com."
veil = Veil.high(secret=b"memory-secret", scope="session-123")
safe_note = veil.redact_text(raw_note, channel="memory.write")

vectorstore_payload = {"text": safe_note.text, "metadata": {"redacted": True}}
print(vectorstore_payload)
