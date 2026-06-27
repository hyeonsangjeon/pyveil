"""Utility functions for pyveil."""

import json
from typing import Any, Dict, Iterable, Mapping


def luhn_valid(value: str) -> bool:
    """Return true when ``value`` passes the Luhn checksum."""

    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def json_pointer(path: Iterable[Any]) -> str:
    """Build a JSON Pointer for a structured-data path."""

    parts = []
    for part in path:
        text = str(part).replace("~", "~0").replace("/", "~1")
        parts.append(text)
    return "/" + "/".join(parts) if parts else ""


def safe_string(value: Any) -> str:
    """Convert a value to a deterministic string for fingerprinting."""

    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def stats_counts(types: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entity_type in types:
        counts[entity_type] = counts.get(entity_type, 0) + 1
    return counts


def looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def clone_mapping(mapping: Mapping[Any, Any]) -> Dict[Any, Any]:
    return dict(mapping)
