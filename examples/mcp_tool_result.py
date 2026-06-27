"""MCP-style tool result redaction."""

from pyveil import Veil
from pyveil.integrations import redact_tool_result

raw_result = {
    "customer": "alice@example.com",
    "phone": "010-1234-5678",
}

veil = Veil.high(secret=b"mcp-secret")
safe_result = redact_tool_result(raw_result, veil=veil)
print(safe_result)
