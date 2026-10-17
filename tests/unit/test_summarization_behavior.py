from unittest.mock import MagicMock

import pytest

from src.agents.summarization import SummarizationError, summarize
from src.graph.state import (
    ResolutionStatus,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)


def _transcript() -> TranscriptionResult:
    return TranscriptionResult(
        call_id="summary-call",
        full_text="",
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=65.9,
                end_time=68.2,
                speaker="Agent",
                text="How can I help?",
                confidence=0.9,
            )
        ],
    )


def _summary() -> SummaryResult:
    return SummaryResult(
        call_id="wrong-id",
        call_purpose="Support request",
        key_discussion_points=["Issue", "Review", "Next step"],
        resolution_status=ResolutionStatus.UNRESOLVED,
        sentiment_trajectory="neutral",
    )


def _config(retries=2):
    return MagicMock(
        llm_provider="openai",
        llm_timeout_seconds=30,
        max_retries_per_node=retries,
    )


def test_summarize_formats_timestamped_transcript_and_retries(monkeypatch):
    structured = MagicMock()
    structured.invoke.side_effect = [RuntimeError("temporary"), _summary()]
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    monkeypatch.setattr("src.agents.summarization.load_config", lambda: _config())
    monkeypatch.setattr("src.agents.summarization.get_llm", lambda **_: llm)
    monkeypatch.setattr("src.agents.summarization.time.sleep", lambda _: None)

    result = summarize(_transcript())

    assert result.call_id == "summary-call"
    assert structured.invoke.call_count == 2
    message = structured.invoke.call_args.args[0][1].content
    assert "[01:05-01:08] Agent: How can I help?" in message


def test_summarize_exhausted_retries_raise_domain_error(monkeypatch):
    structured = MagicMock()
    structured.invoke.side_effect = RuntimeError("provider unavailable")
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    monkeypatch.setattr("src.agents.summarization.load_config", lambda: _config(retries=2))
    monkeypatch.setattr("src.agents.summarization.get_llm", lambda **_: llm)
    monkeypatch.setattr("src.agents.summarization.time.sleep", lambda _: None)

    with pytest.raises(SummarizationError, match="Failed to summarize transcript"):
        summarize(_transcript())

    assert structured.invoke.call_count == 2
