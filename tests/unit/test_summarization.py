from unittest.mock import MagicMock

from src.agents.summarization import summarize
from src.graph.state import (
    ResolutionStatus,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)


def make_transcript():
    return TranscriptionResult(
        call_id="call-123",
        full_text="Hello. I need help with my bill.",
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=0.0,
                end_time=3.0,
                speaker="Agent",
                text="Hello, how can I help?",
                confidence=0.95,
            ),
            TranscriptionSegment(
                start_time=3.0,
                end_time=7.0,
                speaker="Customer",
                text="I need help with my bill.",
                confidence=0.92,
            ),
        ],
    )


def make_summary():
    return SummaryResult(
        call_id="wrong-id",
        call_purpose="Customer needs help with a billing issue.",
        key_discussion_points=[
            "Customer contacted support about a bill.",
            "Agent offered assistance.",
            "Billing issue was discussed.",
        ],
        action_items=[],
        resolution_status=ResolutionStatus.UNRESOLVED,
        sentiment_trajectory="neutral",
        entities=[],
    )


def test_summarize_returns_summary_with_transcript_call_id(monkeypatch):
    transcript = make_transcript()
    fake_summary = make_summary()

    structured_llm = MagicMock()
    structured_llm.invoke.return_value = fake_summary

    base_llm = MagicMock()
    base_llm.with_structured_output.return_value = structured_llm

    fake_config = MagicMock(llm_provider="openai", llm_timeout_seconds=30, max_retries_per_node=3)
    monkeypatch.setattr("src.agents.summarization.get_llm", lambda **kwargs: base_llm)

    monkeypatch.setattr(
        "src.agents.summarization.load_config",
        lambda: fake_config,
    )

    result = summarize(transcript)

    assert isinstance(result, SummaryResult)
    assert result.call_id == transcript.call_id
