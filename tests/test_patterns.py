import pytest

from pyveil import Action, BlockedSensitiveData, Channel, CustomRule, Policy, Veil
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


def test_detects_email_before_trailing_sentence_punctuation():
    veil = Veil.high(secret=b"test-secret")

    result = veil.redact_text("Reach alice@example.com.")

    assert "alice@example.com" not in result.text
    assert result.text.startswith("Reach [EMAIL:")
    assert result.text.endswith("].")


def test_email_enclosing_e164_shaped_plus_tag_wins_overlap():
    email = "user+14155550199@example.com"

    result = Veil.high(secret=b"test-secret").redact_text(email)

    assert finding_types(result) == {"EMAIL"}
    assert email not in result.text
    assert result.text.startswith("[EMAIL:")


def test_phone_pass_policy_cannot_expose_enclosing_email():
    email = "user+14155550199@example.com"
    policy = Policy.default_high().override(
        Channel.PROMPT_INPUT,
        "PHONE",
        Action.PASS,
    )

    result = Veil.high(secret=b"test-secret", policy=policy).redact_text(email)

    assert finding_types(result) == {"EMAIL"}
    assert email not in result.text


def test_inner_custom_rule_does_not_suppress_enclosing_email():
    email = "user+14155550199@example.com"
    veil = Veil.high(
        secret=b"test-secret",
        rules=[CustomRule.exact("PERSON", "user")],
    )

    result = veil.redact_text(email)

    assert finding_types(result) == {"EMAIL"}
    assert email not in result.text
    assert result.text.startswith("[EMAIL:")


@pytest.mark.parametrize(
    "known_value",
    [
        "Alice alice@example.com Smith",
        "Alice +14155550199 Smith",
    ],
)
def test_enclosing_exact_custom_rule_wins_email_and_phone_overlaps(known_value):
    veil = Veil.high(
        secret=b"test-secret",
        rules=[CustomRule.exact("PERSON", known_value)],
    )

    result = veil.redact_text(known_value)

    assert finding_types(result) == {"PERSON"}
    assert known_value not in result.text
    assert result.text.startswith("[PERSON:")


def test_custom_block_action_is_preserved_for_e164_exact_rule():
    phone = "+14155550199"
    policy = Policy.default_high().override(
        Channel.PROMPT_INPUT,
        "KNOWN_PHONE",
        Action.BLOCK,
    )
    veil = Veil.high(
        secret=b"test-secret",
        policy=policy,
        rules=[CustomRule.exact("KNOWN_PHONE", phone)],
    )

    with pytest.raises(BlockedSensitiveData):
        veil.redact_text(phone, channel=Channel.PROMPT_INPUT)


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


@pytest.mark.parametrize("scheme", ["Bearer", "Basic", "Token", "ApiKey"])
def test_detects_common_authorization_header_schemes(scheme):
    veil = Veil.high(secret=b"test-secret")
    credential = "DEMO_ONLY_CREDENTIAL_123456"

    result = veil.redact_text(f"Authorization: {scheme} {credential}")

    assert finding_types(result) == {"AUTH_HEADER"}
    assert credential not in result.text
    assert result.text.startswith("[AUTH_HEADER:")


def test_authorization_header_redacts_composite_credential_suffixes():
    veil = Veil.high(secret=b"test-secret")
    text = "Authorization: ApiKey credential=client123,signature=demo-only-signature"

    result = veil.redact_text(text)

    assert finding_types(result) == {"AUTH_HEADER"}
    assert "client123" not in result.text
    assert "demo-only-signature" not in result.text
    assert result.text.startswith("[AUTH_HEADER:")


def test_authorization_header_does_not_consume_the_next_line():
    veil = Veil.high(secret=b"test-secret")
    text = "Authorization: Token\nContent-Type: application/json"

    result = veil.redact_text(text)

    assert result.findings == ()
    assert result.text == text


@pytest.mark.parametrize("phone", ["+14155550199", "+821012345678"])
def test_detects_compact_e164_phone_numbers(phone):
    veil = Veil.high(secret=b"test-secret")

    result = veil.redact_text(f"call {phone}")

    assert finding_types(result) == {"PHONE"}
    assert phone not in result.text


def test_low_masks_every_detected_e164_phone():
    phone = "+67712345"

    result = Veil.low(secret=b"test-secret").redact_text(phone)

    assert finding_types(result) == {"PHONE"}
    assert result.text != phone
    assert "*" in result.text


def test_plus_prefixed_luhn_valid_number_is_classified_as_phone():
    phone = "+8613812345678"

    result = Veil.high(secret=b"test-secret").redact_text(phone)

    assert finding_types(result) == {"PHONE"}
    assert result.findings[0].detector == "phone"
    assert phone not in result.text


def test_plus_prefixed_card_longer_than_e164_is_still_redacted():
    card = "+4242424242424242"

    result = Veil.high(secret=b"test-secret").redact_text(card)

    assert finding_types(result) == {"CREDIT_CARD"}
    assert result.findings[0].detector == "credit_card"
    assert card not in result.text


@pytest.mark.parametrize(
    "text",
    [
        "Authorization: Token short",
        "version +1415",
        "reference 1234567890123456",
    ],
)
def test_new_detector_shapes_stay_conservative(text):
    veil = Veil.high(secret=b"test-secret")

    result = veil.redact_text(text)

    assert result.findings == ()
    assert result.text == text


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
