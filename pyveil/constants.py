"""Public channel and entity constants."""

from enum import Enum
from typing import Union


class Channel(str, Enum):
    """Known context channels for policy decisions."""

    PROMPT_INPUT = "prompt.input"
    PROMPT_OUTPUT = "prompt.output"
    TOOL_CALL_ARGUMENTS = "tool.call.arguments"
    TOOL_CALL_RESULT = "tool.call.result"
    MCP_RESOURCE_CONTENT = "mcp.resource.content"
    MEMORY_WRITE = "memory.write"
    TRACE_SPAN_ATTRIBUTES = "trace.span.attributes"
    LOG_RECORD = "log.record"


class Entity(str, Enum):
    """Known sensitive entity types emitted by built-in detectors."""

    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CREDIT_CARD = "CREDIT_CARD"
    JWT = "JWT"
    AUTH_HEADER = "AUTH_HEADER"
    PRIVATE_KEY = "PRIVATE_KEY"
    API_KEY = "API_KEY"
    URL_QUERY_SECRET = "URL_QUERY_SECRET"
    KV_SECRET = "KV_SECRET"


ChannelLike = Union[str, Channel]
EntityLike = Union[str, Entity]


def normalize_channel(channel: ChannelLike) -> str:
    """Return a plain channel string."""

    if isinstance(channel, Channel):
        return channel.value
    return str(channel)


def normalize_entity(entity: EntityLike) -> str:
    """Return a plain entity string."""

    if isinstance(entity, Entity):
        return entity.value
    return str(entity)
