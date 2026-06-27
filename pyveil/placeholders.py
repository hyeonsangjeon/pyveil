"""Stable HMAC placeholders."""

import hashlib
import hmac
from typing import Tuple, Union

Secret = Union[str, bytes, bytearray]


def normalize_secret(secret: Secret) -> bytes:
    """Normalize a user-provided HMAC secret."""

    if isinstance(secret, str):
        value = secret.encode("utf-8")
    elif isinstance(secret, (bytes, bytearray)):
        value = bytes(secret)
    else:
        raise TypeError("secret must be str or bytes")
    if not value:
        raise ValueError("secret must not be empty")
    return value


def fingerprint(
    entity_type: str,
    value: str,
    secret: bytes,
    scope: str = "default",
    length: int = 12,
) -> str:
    """Return a scoped HMAC digest for a sensitive value."""

    if length < 8:
        raise ValueError("placeholder digest length must be at least 8")
    message = f"{scope}\x00{entity_type}\x00{value}"
    digest = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:length]


def placeholder(
    entity_type: str,
    value: str,
    secret: bytes,
    scope: str = "default",
    length: int = 12,
) -> Tuple[str, str]:
    """Return ``([TYPE:digest], digest)``."""

    digest = fingerprint(entity_type, value, secret=secret, scope=scope, length=length)
    return f"[{entity_type}:{digest}]", digest
