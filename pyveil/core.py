"""Core pyveil redaction engine."""

import json
import os
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from .constants import ChannelLike, normalize_channel
from .detectors import DetectedValue, detect_text, entity_for_key, is_sensitive_key
from .exceptions import BlockedSensitiveData
from .findings import Finding, RedactionResult, RedactionStats
from .levels import Action, Level
from .masking import mask_value
from .placeholders import Secret, normalize_secret, placeholder
from .policy import Policy
from .rules import CustomRule
from .utils import json_pointer, looks_like_json, safe_string, stats_counts


class Veil:
    """Boundary-aware redaction facade for LLM and agent applications.

    ``policy`` takes precedence over ``level`` when both are supplied.
    Build one ``Veil`` per tenant, session, or run and reuse it in tight loops.
    """

    def __init__(
        self,
        secret: Secret,
        level: Level = Level.HIGH,
        scope: str = "default",
        policy: Optional[Policy] = None,
        placeholder_length: int = 12,
        max_input_chars: Optional[int] = 1_000_000,
        rules: Sequence[CustomRule] = (),
    ) -> None:
        if secret is None:
            raise ValueError("secret is required for stable HMAC placeholders")
        self.secret = normalize_secret(secret)
        self.scope = scope
        self.policy = policy or Policy(default_level=level)
        self.placeholder_length = placeholder_length
        self.max_input_chars = max_input_chars
        self.rules = tuple(rules)
        if not all(isinstance(rule, CustomRule) for rule in self.rules):
            raise TypeError("rules must contain CustomRule instances")

    @classmethod
    def high(
        cls,
        secret: Secret,
        scope: str = "default",
        policy: Optional[Policy] = None,
        max_input_chars: Optional[int] = 1_000_000,
        rules: Sequence[CustomRule] = (),
    ) -> "Veil":
        """Create a HIGH redactor for agent/model/tool boundaries."""

        return cls(
            secret=secret,
            level=Level.HIGH,
            scope=scope,
            policy=policy,
            max_input_chars=max_input_chars,
            rules=rules,
        )

    @classmethod
    def low(
        cls,
        secret: Secret,
        scope: str = "default",
        policy: Optional[Policy] = None,
        max_input_chars: Optional[int] = 1_000_000,
        rules: Sequence[CustomRule] = (),
    ) -> "Veil":
        """Create a LOW redactor for human-facing diagnostic previews."""

        return cls(
            secret=secret,
            level=Level.LOW,
            scope=scope,
            policy=policy or Policy.default_low(),
            max_input_chars=max_input_chars,
            rules=rules,
        )

    def redact_text(self, text: str, channel: ChannelLike = "prompt.input") -> RedactionResult:
        """Redact sensitive values in a string."""

        if not isinstance(text, str):
            raise TypeError("redact_text expects a string")
        self._check_input_size(len(text))
        channel_value = normalize_channel(channel)
        redacted, findings, blocked = self._redact_string(text, channel=channel_value, path=None)
        if blocked:
            raise BlockedSensitiveData(channel_value, blocked)
        return self._result(redacted, findings)

    def redact_data(
        self, data: Any, channel: ChannelLike = "tool.call.arguments"
    ) -> RedactionResult:
        """Redact sensitive values in dict/list data or JSON strings."""

        channel_value = normalize_channel(channel)
        original_was_json = False
        value = data
        if isinstance(data, str) and looks_like_json(data):
            self._check_input_size(len(data))
            try:
                value = json.loads(data)
                original_was_json = True
            except json.JSONDecodeError:
                return self.redact_text(data, channel=channel_value)
        elif isinstance(data, str):
            return self.redact_text(data, channel=channel_value)
        else:
            self._check_input_size(self._string_size(data))

        findings: List[Finding] = []
        blocked: List[Finding] = []
        redacted = self._redact_node(
            value, channel=channel_value, path=(), findings=findings, blocked=blocked
        )
        if blocked:
            raise BlockedSensitiveData(channel_value, blocked)
        if original_was_json:
            redacted = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"))
        return self._result(redacted, findings)

    def _redact_node(
        self,
        value: Any,
        channel: str,
        path: Tuple[Any, ...],
        findings: List[Finding],
        blocked: List[Finding],
    ) -> Any:
        if isinstance(value, dict):
            redacted_mapping = {}
            for key, child in value.items():
                child_path = path + (key,)
                if is_sensitive_key(key):
                    redacted_mapping[key] = self._redact_keyed_value(
                        key,
                        child,
                        channel=channel,
                        path=child_path,
                        findings=findings,
                        blocked=blocked,
                    )
                else:
                    redacted_mapping[key] = self._redact_node(
                        child, channel=channel, path=child_path, findings=findings, blocked=blocked
                    )
            return redacted_mapping
        if isinstance(value, list):
            return [
                self._redact_node(
                    item, channel=channel, path=path + (index,), findings=findings, blocked=blocked
                )
                for index, item in enumerate(value)
            ]
        if isinstance(value, tuple):
            return tuple(
                self._redact_node(
                    item, channel=channel, path=path + (index,), findings=findings, blocked=blocked
                )
                for index, item in enumerate(value)
            )
        if isinstance(value, str):
            redacted, text_findings, text_blocked = self._redact_string(
                value, channel=channel, path=json_pointer(path)
            )
            findings.extend(text_findings)
            blocked.extend(text_blocked)
            return redacted
        return value

    def _redact_keyed_value(
        self,
        key: object,
        value: Any,
        channel: str,
        path: Tuple[Any, ...],
        findings: List[Finding],
        blocked: List[Finding],
    ) -> Any:
        if not isinstance(value, str):
            if isinstance(value, (dict, list, tuple)):
                return self._redact_node(
                    value, channel=channel, path=path, findings=findings, blocked=blocked
                )
            return value
        entity_type = entity_for_key(key, value)
        source = safe_string(value)
        stable_placeholder, digest = placeholder(
            entity_type,
            source,
            secret=self.secret,
            scope=self.scope,
            length=self.placeholder_length,
        )

        finding = Finding(
            type=entity_type,
            detector="key_name",
            rule_id="structured_sensitive_key",
            confidence=1.0,
            path=json_pointer(path),
            placeholder=stable_placeholder,
            fingerprint=digest,
        )
        findings.append(finding)
        action = self.policy.action_for(channel, entity_type)
        if action == Action.BLOCK:
            blocked.append(finding)
        if action == Action.PASS:
            return value
        level = self.policy.level_for(channel)
        return mask_value(entity_type, source, level, stable_placeholder)

    def _redact_string(
        self,
        text: str,
        channel: str,
        path: Optional[str],
    ) -> Tuple[str, List[Finding], List[Finding]]:
        replacements = []
        findings: List[Finding] = []
        blocked: List[Finding] = []
        for detected in detect_text(text, rules=self.rules):
            finding, replacement = self._finding_and_replacement(
                detected, text, channel=channel, path=path
            )
            findings.append(finding)
            action = self.policy.action_for(channel, detected.type)
            if action == Action.BLOCK:
                blocked.append(finding)
            elif action == Action.REDACT:
                replacements.append((detected.start, detected.end, replacement))

        redacted = text
        for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
            redacted = redacted[:start] + replacement + redacted[end:]
        return redacted, findings, blocked

    def _finding_and_replacement(
        self,
        detected: DetectedValue,
        original_text: str,
        channel: str,
        path: Optional[str],
    ) -> Tuple[Finding, str]:
        stable_placeholder, digest = placeholder(
            detected.type,
            detected.value,
            secret=self.secret,
            scope=self.scope,
            length=self.placeholder_length,
        )
        level = self.policy.level_for(channel)
        replacement = mask_value(detected.type, detected.value, level, stable_placeholder)
        finding = Finding(
            type=detected.type,
            detector=detected.detector,
            rule_id=detected.rule_id,
            confidence=detected.confidence,
            start=detected.start,
            end=detected.end,
            path=path,
            placeholder=stable_placeholder,
            fingerprint=digest,
        )
        return finding, replacement

    def _result(self, data: Any, findings: Iterable[Finding]) -> RedactionResult:
        finding_tuple = tuple(findings)
        return RedactionResult(
            data=data,
            findings=finding_tuple,
            stats=RedactionStats(
                total_findings=len(finding_tuple),
                counts_by_type=stats_counts(finding.type for finding in finding_tuple),
            ),
        )

    def _check_input_size(self, size: int) -> None:
        if self.max_input_chars is not None and size > self.max_input_chars:
            raise ValueError("input exceeds max_input_chars")

    def _string_size(self, value: Any) -> int:
        if isinstance(value, str):
            return len(value)
        if isinstance(value, dict):
            return sum(len(str(key)) + self._string_size(child) for key, child in value.items())
        if isinstance(value, (list, tuple)):
            return sum(self._string_size(item) for item in value)
        return 0


def redact_text(
    text: str,
    channel: ChannelLike = "prompt.input",
    *,
    secret: Optional[Secret] = None,
    scope: str = "default",
    level: Level = Level.HIGH,
    policy: Optional[Policy] = None,
    placeholder_length: int = 12,
    max_input_chars: Optional[int] = 1_000_000,
    rules: Sequence[CustomRule] = (),
) -> RedactionResult:
    """Redact text with a one-shot ``Veil`` instance.

    Pass ``secret=...`` explicitly or set ``PYVEIL_SECRET`` in the environment.
    """

    veil = _one_shot_veil(
        secret=secret,
        scope=scope,
        level=level,
        policy=policy,
        placeholder_length=placeholder_length,
        max_input_chars=max_input_chars,
        rules=rules,
    )
    return veil.redact_text(text, channel=channel)


def redact_data(
    data: Any,
    channel: ChannelLike = "tool.call.arguments",
    *,
    secret: Optional[Secret] = None,
    scope: str = "default",
    level: Level = Level.HIGH,
    policy: Optional[Policy] = None,
    placeholder_length: int = 12,
    max_input_chars: Optional[int] = 1_000_000,
    rules: Sequence[CustomRule] = (),
) -> RedactionResult:
    """Redact structured data with a one-shot ``Veil`` instance.

    Pass ``secret=...`` explicitly or set ``PYVEIL_SECRET`` in the environment.
    """

    veil = _one_shot_veil(
        secret=secret,
        scope=scope,
        level=level,
        policy=policy,
        placeholder_length=placeholder_length,
        max_input_chars=max_input_chars,
        rules=rules,
    )
    return veil.redact_data(data, channel=channel)


def _one_shot_veil(
    *,
    secret: Optional[Secret],
    scope: str,
    level: Level,
    policy: Optional[Policy],
    placeholder_length: int,
    max_input_chars: Optional[int],
    rules: Sequence[CustomRule],
) -> Veil:
    resolved_secret = secret or os.environ.get("PYVEIL_SECRET")
    if resolved_secret is None:
        raise ValueError("secret is required; pass secret=... or set PYVEIL_SECRET")
    return Veil(
        secret=resolved_secret,
        level=level,
        scope=scope,
        policy=policy,
        placeholder_length=placeholder_length,
        max_input_chars=max_input_chars,
        rules=rules,
    )
