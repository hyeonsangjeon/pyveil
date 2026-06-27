"""Redact Python logging output before handlers export it."""

import logging

from pyveil import Veil
from pyveil.integrations import PyVeilLogFilter

logger = logging.getLogger("demo")
handler = logging.StreamHandler()
handler.addFilter(PyVeilLogFilter(Veil.high(secret=b"log-secret")))
logger.addHandler(handler)
logger.warning("user email is alice@example.com")
