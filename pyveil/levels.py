"""Public redaction levels and policy actions."""

from enum import Enum


class Level(str, Enum):
    """Redaction strength."""

    LOW = "LOW"
    HIGH = "HIGH"


class Action(str, Enum):
    """Policy action for a detected sensitive value."""

    REDACT = "REDACT"
    BLOCK = "BLOCK"
    PASS = "PASS"
