from unittest.mock import Mock

import pytest

from src.graph import nodes
from src.graph.state import PipelineState, TranscriptionResult, TranscriptionSegment


def transcript(text, segment_text=None):
    return TranscriptionResult(
        call_id="call-safe",
        language="en",
        full_text=text,
        segments=[
            TranscriptionSegment(
                start_time=1.25,
                end_time=4.5,
                speaker="Customer",
                confidence=0.87,
                text=text if segment_text is None else segment_text,
            )
        ],
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Email jane@co.com or call 555-123-4567.",
            "Email [REDACTED_EMAIL] or call [REDACTED_PHONE].",
        ),
        (
            "SSN 123-45-6789, card 4111-1111-1111-1111.",
            "SSN [REDACTED_SSN], card [REDACTED_CREDIT_CARD].",
        ),
        ("Hello, how can I help?", "Hello, how can I help?"),
    ],
)
def test_redaction_preserves_raw_and_metadata(text, expected):
    raw = transcript(text)
    before = raw.model_dump()
    state = {"transcription": raw}
    update = nodes.pii_redaction_node(state)
    state.update(update)
    safe = state["sanitized_transcription"]

    assert "transcription" not in update
    assert state["transcription"] is raw
    assert raw.model_dump() == before
    assert isinstance(safe, TranscriptionResult)
    assert safe is not raw
    assert safe.full_text == safe.segments[0].text == expected
    assert safe.segments[0] is not raw.segments[0]
    assert safe.model_dump(exclude={"full_text", "segments"}) == raw.model_dump(
        exclude={"full_text", "segments"}
    )
    assert safe.segments[0].model_dump(exclude={"text"}) == raw.segments[0].model_dump(
        exclude={"text"}
    )
    assert update["pii_result"].redacted_text == expected
    assert update["pii_result"].pii_found is (text != expected)
    assert {
        "transcription",
        "sanitized_transcription",
        "pii_result",
    } <= PipelineState.__optional_keys__


def test_segment_only_pii_is_redacted_and_recorded():
    raw = transcript("Contact provided.", "Email jane@co.com.")
    result = nodes.pii_redaction_node({"transcription": raw})
    assert result["sanitized_transcription"].full_text == "Contact provided."
    assert result["sanitized_transcription"].segments[0].text == "Email [REDACTED_EMAIL]."
    assert result["pii_result"].pii_found is True
    assert raw.segments[0].text == "Email jane@co.com."


def test_pii_split_across_segments_is_not_preserved():
    raw = TranscriptionResult(
        call_id="call-safe",
        language="en",
        full_text="Card 4111 1111 1111 1111",
        segments=[
            TranscriptionSegment(
                start_time=0,
                end_time=1,
                speaker="Customer",
                confidence=0.9,
                text="Card 4111 1111",
            ),
            TranscriptionSegment(
                start_time=1,
                end_time=2,
                speaker="Customer",
                confidence=0.9,
                text="1111 1111",
            ),
        ],
    )

    safe = nodes.pii_redaction_node({"transcription": raw})["sanitized_transcription"]

    assert safe.full_text == "Card [REDACTED_CREDIT_CARD]"
    assert "4111" not in " ".join(segment.text for segment in safe.segments)


def test_full_text_is_redacted_without_segments():
    raw = transcript("Email jane@co.com.")
    raw.segments = []
    safe = nodes.pii_redaction_node({"transcription": raw})["sanitized_transcription"]
    assert safe.full_text == "Email [REDACTED_EMAIL]."
    assert safe.segments == []


@pytest.mark.parametrize(
    "node, consumer, output_key",
    [
        (nodes.summarization_node, "summarize", "summary"),
        (nodes.qa_node, "score_qa", "qa_scores"),
        (nodes.report_node, "build_report", "report"),
    ],
)
def test_downstream_uses_safe_transcript_and_never_falls_back(
    monkeypatch,
    node,
    consumer,
    output_key,
):
    raw = transcript("Email jane@co.com.")
    state = {
        "transcription": raw,
        "intake": object(),
        "summary": object(),
        "qa_scores": object(),
    }
    state.update(nodes.pii_redaction_node(state))
    safe = state["sanitized_transcription"]
    call = Mock()
    monkeypatch.setattr(nodes, consumer, call)
    # Mock database operations for report_node
    if consumer == "build_report":
        monkeypatch.setattr(nodes, "save_call_analysis", Mock())
        monkeypatch.setattr(nodes, "_log_event", Mock())

    expected = {output_key: call.return_value}
    if node is nodes.report_node:
        expected["status"] = "completed"
    assert node(state) == expected
    if consumer == "summarize":
        call.assert_called_once_with(safe)
        assert call.call_args.args[0] is safe
    elif consumer == "score_qa":
        call.assert_called_once_with(transcript=safe, summary=state["summary"])
        assert call.call_args.kwargs["transcript"] is safe
    else:
        call.assert_called_once_with(
            intake=state["intake"],
            transcription=safe,
            summary=state["summary"],
            qa_scores=state["qa_scores"],
        )
        assert call.call_args.kwargs["transcription"] is safe

    call.reset_mock()
    del state["sanitized_transcription"]
    with pytest.raises(KeyError, match="sanitized_transcription"):
        node(state)
    call.assert_not_called()
