"""User-defined rules for known values and domain identifiers."""

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Match, Pattern, Union, cast

PatternSource = Union[str, Pattern[str]]


@dataclass(frozen=True)
class CustomRule:
    """A trusted application-defined detector rule.

    Use a regex string or compiled pattern for structured domain identifiers.
    Use :meth:`exact` when the application already knows the sensitive values,
    such as customer names loaded from an authenticated record.
    """

    entity: str
    pattern: PatternSource = field(repr=False)
    rule_id: str = "custom_regex"
    detector: str = "custom_rule"
    confidence: float = 1.0
    priority: int = 65

    def __post_init__(self) -> None:
        entity = str(self.entity).strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", entity):
            raise ValueError("custom rule entity must match [A-Z][A-Z0-9_]{0,63}")
        if not self.rule_id:
            raise ValueError("custom rule rule_id must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("custom rule confidence must be between 0 and 1")
        if self.priority < 0:
            raise ValueError("custom rule priority must be non-negative")

        if isinstance(self.pattern, str):
            compiled = re.compile(self.pattern)
        elif isinstance(self.pattern, re.Pattern) and isinstance(self.pattern.pattern, str):
            compiled = self.pattern
        else:
            raise TypeError("custom rule pattern must be a string or compiled text regex")
        object.__setattr__(self, "entity", entity)
        object.__setattr__(self, "pattern", compiled)

    def finditer(self, text: str) -> Iterator[Match[str]]:
        """Return non-overlapping matches from the compiled rule pattern."""

        return cast(Pattern[str], self.pattern).finditer(text)

    @classmethod
    def exact(
        cls,
        entity: str,
        values: Union[str, Iterable[str]],
        *,
        ignore_case: bool = False,
        word_boundaries: bool = True,
        rule_id: str = "",
        priority: int = 65,
    ) -> "CustomRule":
        """Build a rule from values the application already knows are sensitive."""

        source_values = (values,) if isinstance(values, str) else tuple(values)
        unique_values = sorted(
            {value for value in source_values if value},
            key=lambda value: (-len(value), value),
        )
        if not unique_values:
            raise ValueError("exact custom rule requires at least one non-empty value")
        expression = "(?:" + "|".join(re.escape(value) for value in unique_values) + ")"
        if word_boundaries:
            expression = r"(?<!\w)" + expression + r"(?!\w)"
        flags = re.IGNORECASE if ignore_case else 0
        normalized_entity = str(entity).strip().upper()
        return cls(
            entity=normalized_entity,
            pattern=re.compile(expression, flags),
            rule_id=rule_id or "known_" + normalized_entity.lower(),
            detector="known_value",
            priority=priority,
        )
