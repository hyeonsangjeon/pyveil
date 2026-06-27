import json

from pyveil import Veil
from pyveil.utils import json_pointer, luhn_valid


def test_luhn_validation():
    assert luhn_valid("4242 4242 4242 4242")
    assert not luhn_valid("1234 5678 9012 3456")


def test_json_pointer_escaping():
    assert json_pointer(("headers", "x/a~b")) == "/headers/x~1a~0b"


def test_structured_data_redacts_nested_values_and_paths():
    veil = Veil.high(secret=b"test-secret", scope="structured")
    payload = {
        "user": "alice@example.com",
        "profile": {
            "phone": "010-1234-5678",
            "url": "https://example.test?token=synthetic-token",
        },
        "password": "synthetic-password",
        "debug": True,
    }

    result = veil.redact_data(payload, channel="prompt.input")

    assert result.data["debug"] is True
    assert result.data["user"].startswith("[EMAIL:")
    assert result.data["profile"]["phone"].startswith("[PHONE:")
    assert "synthetic-token" not in result.data["profile"]["url"]
    assert result.data["password"].startswith("[KV_SECRET:")
    assert {finding.path for finding in result.findings} >= {
        "/user",
        "/profile/phone",
        "/profile/url",
        "/password",
    }


def test_redact_data_accepts_json_string_and_returns_json_string():
    veil = Veil.high(secret=b"test-secret")
    raw = json.dumps({"email": "alice@example.com"})

    result = veil.redact_data(raw, channel="prompt.input")

    assert isinstance(result.data, str)
    assert "alice@example.com" not in result.data
    assert "[EMAIL:" in result.data
