"""Wrap MCP-style tool/resource handlers with pyveil redaction."""

from typing import Any, Callable, Dict

from pyveil import Channel, Veil


def wrap_tool_result(handler: Callable[..., Dict[str, Any]], veil: Veil) -> Callable[..., Dict[str, Any]]:
    def wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        raw_result = handler(*args, **kwargs)
        return veil.redact_data(raw_result, channel=Channel.TOOL_CALL_RESULT).data

    return wrapped


def customer_lookup(customer_id: str) -> Dict[str, Any]:
    return {
        "customer_id": customer_id,
        "email": "alice@example.com",
        "phone": "+82 10-1234-5678",
        "api_key": "demo-api-key-0000-FAKE",
    }


if __name__ == "__main__":
    veil = Veil.high(secret=b"mcp-secret", scope="server-1")
    safe_lookup = wrap_tool_result(customer_lookup, veil)
    print(safe_lookup("customer-123"))
