"""Masking strategies for LOW and HIGH levels."""

import re

from .levels import Level


def mask_value(entity_type: str, value: str, level: Level, stable_placeholder: str) -> str:
    """Mask a detected value according to level."""

    if level == Level.HIGH:
        return stable_placeholder
    if entity_type == "EMAIL":
        return _mask_email_low(value)
    if entity_type == "PHONE":
        return _mask_phone_low(value)
    if entity_type == "CREDIT_CARD":
        return _mask_card_low(value)
    return f"[{entity_type}]"


def _mask_email_low(value: str) -> str:
    local, sep, domain = value.partition("@")
    if not sep:
        return "[EMAIL]"
    domain_parts = domain.rsplit(".", 1)
    if len(domain_parts) == 2:
        domain_name, suffix = domain_parts
        masked_domain = f"{_mask_segment(domain_name, keep=1)}.{suffix}"
    else:
        masked_domain = _mask_segment(domain, keep=1)
    return f"{_mask_segment(local, keep=2)}@{masked_domain}"


def _mask_segment(value: str, keep: int) -> str:
    if not value:
        return "*"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + ("*" * (len(value) - keep))


def _mask_phone_low(value: str) -> str:
    digits = [char for char in value if char.isdigit()]
    if len(digits) < 7:
        return "[PHONE]"
    visible_budget = len(digits) - 2
    prefix_target = 4 if value.strip().startswith("+") else 3
    prefix_keep = min(prefix_target, max(1, visible_budget // 2))
    last_keep = min(4, visible_budget - prefix_keep)
    digit_index = 0
    result = []
    for char in value:
        if char.isdigit():
            digit_index += 1
            if digit_index <= prefix_keep or digit_index > len(digits) - last_keep:
                result.append(char)
            else:
                result.append("*")
        else:
            result.append(char)
    return "".join(result)


def _mask_card_low(value: str) -> str:
    digits = [char for char in value if char.isdigit()]
    if len(digits) < 13:
        return "[CREDIT_CARD]"
    digit_index = 0
    result = []
    for char in value:
        if char.isdigit():
            digit_index += 1
            if digit_index > len(digits) - 4:
                result.append(char)
            else:
                result.append("*")
        elif re.match(r"[\s-]", char):
            result.append(char)
        else:
            result.append(char)
    return "".join(result)
