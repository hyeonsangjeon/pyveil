"""pyveil exceptions."""

from typing import Dict, Iterable, Tuple

from .findings import Finding


class BlockedSensitiveData(ValueError):
    """Raised when policy blocks a sensitive value from crossing a channel."""

    def __init__(self, channel: str, findings: Iterable[Finding]) -> None:
        self.channel = channel
        self.findings: Tuple[Finding, ...] = tuple(findings)
        super().__init__(self.summary())

    def summary(self) -> str:
        counts: Dict[str, int] = {}
        for finding in self.findings:
            counts[finding.type] = counts.get(finding.type, 0) + 1
        detail = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        if not detail:
            detail = "none"
        return f"Blocked sensitive data on channel {self.channel} ({detail})"
