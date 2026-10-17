import pytest

from src.security.pii_redactor import redact_segments


@pytest.mark.parametrize(
    "texts,expected",
    [
        (
            ["Card 4111 1111", "1111 1111 please", "Thank you"],
            ["Card [REDACTED_CREDIT_CARD]", " please", "Thank you"],
        ),
        (["SSN 123", "45", "6789 received"], ["SSN [REDACTED_SSN]", "", " received"]),
        (["Hello", "How can I help?"], ["Hello", "How can I help?"]),
    ],
)
def test_redaction_across_segments_preserves_other_turns(texts, expected):
    values, detected = redact_segments(texts)
    assert values == expected
    assert detected == (texts != expected)
