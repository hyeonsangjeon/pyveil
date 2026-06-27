"""Small MCP-style wrapper helpers."""

from typing import Any

from ..core import Veil


def redact_tool_result(result: Any, veil: Veil, channel: str = "tool.call.result") -> Any:
    """Redact a tool result before returning it to a model client."""

    return veil.redact_data(result, channel=channel).data


def redact_resource(resource: Any, veil: Veil, channel: str = "mcp.resource.content") -> Any:
    """Redact an MCP resource payload before exposing it as model context."""

    return veil.redact_data(resource, channel=channel).data
