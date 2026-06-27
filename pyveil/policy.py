"""Channel-aware redaction policy."""

from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, Optional, Tuple

from .constants import ChannelLike, EntityLike, normalize_channel, normalize_entity
from .levels import Action, Level

DEFAULT_CHANNELS = (
    "prompt.input",
    "prompt.output",
    "tool.call.arguments",
    "tool.call.result",
    "mcp.resource.content",
    "memory.write",
    "trace.span.attributes",
    "log.record",
)

DEFAULT_BLOCKED = frozenset(
    {
        ("tool.call.arguments", "AUTH_HEADER"),
        ("tool.call.arguments", "PRIVATE_KEY"),
        ("tool.call.arguments", "API_KEY"),
        ("tool.call.arguments", "JWT"),
        ("tool.call.arguments", "KV_SECRET"),
        ("tool.call.arguments", "URL_QUERY_SECRET"),
    }
)


@dataclass(frozen=True)
class Policy:
    """A small channel-aware policy.

    The default v0.1 policy redacts all supported findings, but blocks
    credentials that should never be model-controlled tool arguments.
    """

    default_level: Level = Level.HIGH
    channel_levels: Optional[Dict[ChannelLike, Level]] = None
    blocked: FrozenSet[Tuple[ChannelLike, EntityLike]] = DEFAULT_BLOCKED
    channel_actions: Optional[Dict[Tuple[ChannelLike, EntityLike], Action]] = None
    _channel_levels: Dict[str, Level] = field(init=False, repr=False, compare=False)
    _channel_actions: Dict[Tuple[str, str], Action] = field(init=False, repr=False, compare=False)
    _blocked: FrozenSet[Tuple[str, str]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_channel_levels",
            {normalize_channel(channel): level for channel, level in (self.channel_levels or {}).items()},
        )
        object.__setattr__(
            self,
            "_channel_actions",
            {_normalize_policy_key(key): action for key, action in (self.channel_actions or {}).items()},
        )
        object.__setattr__(self, "_blocked", frozenset(_normalize_policy_key(key) for key in self.blocked))

    @classmethod
    def default_high(cls) -> "Policy":
        return cls(default_level=Level.HIGH)

    @classmethod
    def default_low(cls) -> "Policy":
        return cls(default_level=Level.LOW)

    def level_for(self, channel: ChannelLike) -> Level:
        channel_value = normalize_channel(channel)
        return self._channel_levels.get(channel_value, self.default_level)

    def action_for(self, channel: ChannelLike, entity_type: EntityLike) -> Action:
        key = (normalize_channel(channel), normalize_entity(entity_type))
        if key in self._channel_actions:
            return self._channel_actions[key]
        if key in self._blocked:
            return Action.BLOCK
        return Action.REDACT

    def override(
        self,
        channel: ChannelLike,
        entity: EntityLike,
        action: Action,
        level: Optional[Level] = None,
    ) -> "Policy":
        blocked = set(self._blocked)
        key = (normalize_channel(channel), normalize_entity(entity))
        channel_actions = dict(self._channel_actions)
        channel_actions[key] = action
        if action == Action.BLOCK:
            blocked.add(key)
        else:
            blocked.discard(key)

        channel_levels = dict(self._channel_levels)
        if level is not None:
            channel_levels[normalize_channel(channel)] = level
        return replace(
            self,
            blocked=frozenset(blocked),
            channel_actions=channel_actions,
            channel_levels=channel_levels,
        )


def _normalize_policy_key(key: Tuple[ChannelLike, EntityLike]) -> Tuple[str, str]:
    return normalize_channel(key[0]), normalize_entity(key[1])
