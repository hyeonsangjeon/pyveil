"""High-precision built-in and application-defined text detectors."""

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Pattern, Sequence, Tuple

from .rules import CustomRule
from .utils import luhn_valid

EMAIL = "EMAIL"
PHONE = "PHONE"
CREDIT_CARD = "CREDIT_CARD"
JWT = "JWT"
AUTH_HEADER = "AUTH_HEADER"
PRIVATE_KEY = "PRIVATE_KEY"
API_KEY = "API_KEY"
URL_QUERY_SECRET = "URL_QUERY_SECRET"
KV_SECRET = "KV_SECRET"


@dataclass(frozen=True)
class DetectedValue:
    type: str
    start: int
    end: int
    value: str
    detector: str
    rule_id: str
    confidence: float = 1.0
    priority: Optional[int] = None


EMAIL_RE = re.compile(
    r"(?<![\w.%+-])([A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,63})(?![\w-])"
)
KOREAN_PHONE_RE = re.compile(r"(?<!\d)(?:\+82[-.\s]?)?0?1[016789][-\s.]?\d{3,4}[-\s.]?\d{4}(?!\d)")
LOCAL_PHONE_RE = re.compile(r"(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-\s.]?\d{4}(?!\d)")
INTL_PHONE_RE = re.compile(r"(?<!\d)\+\d{1,3}[-.\s]\d{2,4}[-.\s]\d{3,4}[-.\s]\d{3,4}(?!\d)")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)
AUTH_HEADER_RE = re.compile(r"(?i)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}")
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)
URL_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:access_token|refresh_token|id_token|token|api[_-]?key|apikey|key|secret|code|auth)=)([^&#\s]+)"
)
KV_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|api[_-]?key|secret|token|access[_-]?token|refresh[_-]?token|cookie)\b\s*[:=]\s*(['\"]?)([^'\"\s,;]+)\2"
)

API_KEY_PATTERNS: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("openai_key", re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-|live-)?[A-Za-z0-9_-]{20,}")),
    ("github_pat", re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{20,}")),
    ("github_token", re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("slack_token", re.compile(r"(?<![A-Za-z0-9-])xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{20,}")),
    ("aws_access_key", re.compile(r"(?<![A-Z0-9])(AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")),
)

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|api[_-]?key|secret|token|access[_-]?token|refresh[_-]?token|authorization|auth[_-]?header|cookie|private[_-]?key|jwt)"
)

PRIORITY = {
    PRIVATE_KEY: 100,
    AUTH_HEADER: 95,
    JWT: 90,
    API_KEY: 85,
    URL_QUERY_SECRET: 80,
    KV_SECRET: 75,
    CREDIT_CARD: 70,
    EMAIL: 60,
    PHONE: 50,
}


def detect_text(text: str, rules: Sequence[CustomRule] = ()) -> Tuple[DetectedValue, ...]:
    """Detect supported sensitive values in free text."""

    matches: List[DetectedValue] = []
    matches.extend(
        _regex_matches(text, PRIVATE_KEY_RE, PRIVATE_KEY, "private_key", "pem_private_key")
    )
    matches.extend(
        _regex_matches(text, AUTH_HEADER_RE, AUTH_HEADER, "auth_header", "authorization_header")
    )
    matches.extend(_regex_matches(text, JWT_RE, JWT, "jwt", "jwt_compact"))
    matches.extend(_api_key_matches(text))
    matches.extend(_url_query_secret_matches(text))
    matches.extend(_kv_secret_matches(text))
    matches.extend(_regex_matches(text, EMAIL_RE, EMAIL, "email", "email_address", group=1))
    matches.extend(_credit_card_matches(text))
    matches.extend(_phone_matches(text))
    matches.extend(_custom_rule_matches(text, rules))
    return _select_non_overlapping(matches)


def is_sensitive_key(key: object) -> bool:
    return bool(SENSITIVE_KEY_RE.search(str(key)))


def entity_for_key(key: object, value: object = None) -> str:
    text = str(key).lower()
    normalized = text.replace("-", "_")
    if "authorization" in normalized or "auth_header" in normalized:
        return AUTH_HEADER
    if "private" in normalized and "key" in normalized:
        return PRIVATE_KEY
    if "api_key" in normalized or "apikey" in normalized:
        return API_KEY
    if "jwt" in normalized:
        return JWT
    if isinstance(value, str) and ("token" in normalized) and JWT_RE.fullmatch(value):
        return JWT
    return KV_SECRET


def _regex_matches(
    text: str,
    pattern: Pattern[str],
    entity_type: str,
    detector: str,
    rule_id: str,
    group: int = 0,
) -> Iterable[DetectedValue]:
    for match in pattern.finditer(text):
        start, end = match.span(group)
        yield DetectedValue(
            type=entity_type,
            start=start,
            end=end,
            value=match.group(group),
            detector=detector,
            rule_id=rule_id,
        )


def _api_key_matches(text: str) -> Iterable[DetectedValue]:
    for rule_id, pattern in API_KEY_PATTERNS:
        for match in pattern.finditer(text):
            yield DetectedValue(
                API_KEY, match.start(), match.end(), match.group(), "api_key", rule_id
            )


def _url_query_secret_matches(text: str) -> Iterable[DetectedValue]:
    for match in URL_QUERY_SECRET_RE.finditer(text):
        start, end = match.span(2)
        yield DetectedValue(
            URL_QUERY_SECRET,
            start,
            end,
            match.group(2),
            "url_query_secret",
            "sensitive_query_parameter",
        )


def _kv_secret_matches(text: str) -> Iterable[DetectedValue]:
    for match in KV_SECRET_RE.finditer(text):
        start, end = match.span(3)
        yield DetectedValue(
            KV_SECRET, start, end, match.group(3), "kv_secret", "text_key_value_secret"
        )


def _credit_card_matches(text: str) -> Iterable[DetectedValue]:
    for match in CREDIT_CARD_RE.finditer(text):
        candidate = match.group()
        digits = "".join(char for char in candidate if char.isdigit())
        if luhn_valid(digits):
            yield DetectedValue(
                CREDIT_CARD,
                match.start(),
                match.end(),
                candidate,
                "credit_card",
                "luhn_card_number",
                confidence=0.98,
            )


def _phone_matches(text: str) -> Iterable[DetectedValue]:
    seen = set()
    for rule_id, pattern in (
        ("korean_mobile_phone", KOREAN_PHONE_RE),
        ("korean_local_phone", LOCAL_PHONE_RE),
        ("international_phone", INTL_PHONE_RE),
    ):
        for match in pattern.finditer(text):
            span = match.span()
            if span in seen:
                continue
            seen.add(span)
            yield DetectedValue(
                PHONE, match.start(), match.end(), match.group(), "phone", rule_id, 0.9
            )


def _custom_rule_matches(text: str, rules: Sequence[CustomRule]) -> Iterable[DetectedValue]:
    for rule in rules:
        for match in rule.finditer(text):
            if match.start() == match.end():
                continue
            yield DetectedValue(
                rule.entity,
                match.start(),
                match.end(),
                match.group(),
                rule.detector,
                rule.rule_id,
                rule.confidence,
                rule.priority,
            )


def _select_non_overlapping(matches: Sequence[DetectedValue]) -> Tuple[DetectedValue, ...]:
    chosen: List[DetectedValue] = []
    occupied: List[Tuple[int, int]] = []
    sorted_matches = sorted(
        matches,
        key=lambda item: (
            -(item.priority if item.priority is not None else PRIORITY.get(item.type, 0)),
            item.start,
            -(item.end - item.start),
        ),
    )
    for match in sorted_matches:
        if any(not (match.end <= start or match.start >= end) for start, end in occupied):
            continue
        chosen.append(match)
        occupied.append((match.start, match.end))
    return tuple(sorted(chosen, key=lambda item: item.start))
