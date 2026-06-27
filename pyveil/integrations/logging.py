"""Logging integration helpers."""

import logging

from ..core import Veil


class PyVeilLogFilter(logging.Filter):
    """Redact log messages before handlers export them."""

    def __init__(self, veil: Veil, channel: str = "log.record") -> None:
        super().__init__()
        self.veil = veil
        self.channel = channel

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        result = self.veil.redact_text(message, channel=self.channel)
        record.msg = result.text
        record.args = ()
        return True
