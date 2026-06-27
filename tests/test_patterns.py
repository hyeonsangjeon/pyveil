from pyveil import Veil
from pyveil.detectors import entity_for_key


def finding_types(result):
    return {finding.type for finding in result.findings}


def test_detects_credit_card_with_luhn_but_not_invalid_card():
    veil = Veil.high(secret=b"test-secret")

    valid = veil.redact_text("card 4242 4242 4242 4242")
    invalid = veil.redact_text("card 1234 5678 9012 3456")

    assert "CREDIT_CARD" in finding_types(valid)
    assert "[CREDIT_CARD:" in valid.text
    assert invalid.findings == ()


def test_detects_jwt_and_api_key():
    veil = Veil.high(secret=b"test-secret")
    token = (
        "jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c "
        "key sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    )

    result = veil.redact_text(token)

    assert {"JWT", "API_KEY"}.issubset(finding_types(result))
    assert "sk-proj-" not in result.text
    assert "eyJhbGci" not in result.text


def test_detects_private_key_and_url_query_secret():
    veil = Veil.high(secret=b"test-secret")
    text = (
        "url https://example.test/callback?access_token=synthetic-token&state=ok\n"
        "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"
    )

    result = veil.redact_text(text)

    assert {"URL_QUERY_SECRET", "PRIVATE_KEY"}.issubset(finding_types(result))
    assert "synthetic-token" not in result.text
    assert "abc123" not in result.text


def test_sensitive_key_entity_mapping_is_specific():
    assert entity_for_key("api_key") == "API_KEY"
    assert entity_for_key("api-key") == "API_KEY"
    assert entity_for_key("apikey") == "API_KEY"
    assert entity_for_key("Authorization") == "AUTH_HEADER"
    assert entity_for_key("auth-header") == "AUTH_HEADER"
    assert entity_for_key("private-key") == "PRIVATE_KEY"
    assert entity_for_key("jwt") == "JWT"
    assert entity_for_key("password") == "KV_SECRET"
    assert (
        entity_for_key(
            "access_token",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        )
        == "JWT"
    )
