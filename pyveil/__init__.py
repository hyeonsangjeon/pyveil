"""pyveil: local PII and secret redaction for Python AI agents."""

__version__ = "0.2.4"
__author__ = "Hyeon Sang Jeon"
__license__ = "MIT"

from .constants import Channel, Entity
from .core import Veil, redact_data, redact_text
from .exceptions import BlockedSensitiveData
from .findings import Finding, RedactionResult, RedactionStats
from .levels import Action, Level
from .policy import Policy
from .rules import CustomRule

__all__ = [
    "Action",
    "BlockedSensitiveData",
    "Channel",
    "CustomRule",
    "Entity",
    "Finding",
    "Level",
    "Policy",
    "RedactionResult",
    "RedactionStats",
    "Veil",
    "redact_data",
    "redact_text",
]
