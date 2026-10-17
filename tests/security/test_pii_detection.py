import pytest

from src.security.pii_redactor import redact_pii

PHONE_SAMPLES = [
    "555-123-4567",
    "(555) 123-4567",
    "555.123.4567",
    "5551234567",
    "+1-555-123-4567",
]

EMAIL_SAMPLES = [
    "jane@co.com",
    "first.last@example.org",
    "user+tag@domain.co.uk",
    "user_name@example.io",
    "first-last@sub.example.com",
]

SSN_SAMPLES = [
    "123-45-6789",
    "123 45 6789",
    "123456789",
    "987-65-4321",
    "987 65 4321",
]

CREDIT_CARD_SAMPLES = [
    "4111111111111111",
    "4111-1111-1111-1111",
    "4111 1111 1111 1111",
    "3782 822463 10005",
    "4222222222222",
]


@pytest.mark.parametrize("phone", PHONE_SAMPLES)
def test_phone_formats_are_redacted(phone):
    result = redact_pii(f"Please call me at {phone} tomorrow.")
    assert result.pii_found is True
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert phone not in result.redacted_text


@pytest.mark.parametrize("email", EMAIL_SAMPLES)
def test_email_formats_are_redacted(email):
    result = redact_pii(f"Send the receipt to {email} please.")
    assert result.pii_found is True
    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert email not in result.redacted_text


@pytest.mark.parametrize("ssn", SSN_SAMPLES)
def test_ssn_formats_are_redacted(ssn):
    result = redact_pii(f"My SSN is {ssn}")
    assert result.pii_found is True
    assert "[REDACTED_SSN]" in result.redacted_text
    assert ssn not in result.redacted_text


@pytest.mark.parametrize("card", CREDIT_CARD_SAMPLES)
def test_credit_card_formats_are_redacted(card):
    result = redact_pii(f"Card number is {card}")
    assert result.pii_found is True
    assert "[REDACTED_CREDIT_CARD]" in result.redacted_text
    assert card not in result.redacted_text


def test_credit_card_split_by_newline_is_redacted():
    result = redact_pii("Card 4111 1111\n1111 1111")
    assert result.pii_found is True
    assert result.redacted_text == "Card [REDACTED_CREDIT_CARD]"


def test_spec_example_ssn_placeholder():
    result = redact_pii("My SSN is 123-45-6789")
    assert "[REDACTED_SSN]" in result.redacted_text
    assert "123-45-6789" not in result.redacted_text


def test_spec_example_phone_and_email_one_pass():
    result = redact_pii("Call 555-123-4567 or email jane@co.com")
    assert result.pii_found is True
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "555-123-4567" not in result.redacted_text
    assert "jane@co.com" not in result.redacted_text


def test_spec_example_clean_text_unchanged():
    text = "Hello, how can I help?"
    result = redact_pii(text)
    assert result.pii_found is False
    assert result.redacted_text == text


def test_pii_embedded_in_conversation_text():
    text = (
        "Agent: I can look that up. What's your SSN?\n"
        "Customer: It's 123-45-6789.\n"
        "Agent: And a callback number?\n"
        "Customer: 555-123-4567, or jane@co.com if email is easier.\n"
        "Agent: Last four of the card ending in the full number "
        "4111-1111-1111-1111 for verification."
    )
    result = redact_pii(text)
    assert result.pii_found is True
    assert "[REDACTED_SSN]" in result.redacted_text
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "[REDACTED_CREDIT_CARD]" in result.redacted_text
    assert "123-45-6789" not in result.redacted_text
    assert "555-123-4567" not in result.redacted_text
    assert "jane@co.com" not in result.redacted_text
    assert "4111-1111-1111-1111" not in result.redacted_text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("5551234567@example.com", "[REDACTED_EMAIL]"),
        ("id-123456789@example.com", "[REDACTED_EMAIL]"),
        ("jane@co.com then jane@co.com", "[REDACTED_EMAIL] then [REDACTED_EMAIL]"),
        (
            "SSN 123456789, phone 5551234567, card 4111111111111111.",
            "SSN [REDACTED_SSN], phone [REDACTED_PHONE], card [REDACTED_CREDIT_CARD].",
        ),
    ],
)
def test_overlapping_and_repeated_pii_preserves_surrounding_text(text, expected):
    assert redact_pii(text).model_dump() == {
        "redacted_text": expected,
        "pii_found": True,
    }
