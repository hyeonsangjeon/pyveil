"""Finding and result models for pyveil."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class Finding:
    """A redaction finding.

    Raw sensitive values are intentionally not stored. The ``raw`` field exists
    to make that contract visible to callers and tests.
    """

    type: str
    detector: str
    rule_id: str
    confidence: float
    start: Optional[int] = None
    end: Optional[int] = None
    path: Optional[str] = None
    placeholder: Optional[str] = None
    fingerprint: Optional[str] = None
    raw: None = None


@dataclass(frozen=True)
class RedactionStats:
    """Small summary of a redaction run."""

    total_findings: int
    counts_by_type: Dict[str, int]


@dataclass(frozen=True)
class RedactionResult:
    """Result returned by text and structured redaction."""

    data: Any
    findings: Tuple[Finding, ...]
    stats: RedactionStats

    @property
    def text(self) -> str:
        """Return the result as text.

        ``redact_text`` always returns a string payload. For structured results,
        callers should use ``data`` directly.
        """

        if not isinstance(self.data, str):
            raise TypeError("This redaction result does not contain text data.")
        return self.data
