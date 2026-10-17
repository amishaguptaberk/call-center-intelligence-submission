from unittest.mock import MagicMock

import pytest

from src.agents.qa_scoring import QAScoringError, score_qa
from src.graph.state import (
    QADimensionScore,
    QAScoreResult,
    ResolutionStatus,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)


def _transcript() -> TranscriptionResult:
    return TranscriptionResult(
        call_id="call-qa-1",
        full_text="Hello. I can help.",
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=0.0,
                end_time=3.0,
                speaker="Agent",
                text="Hello, how can I help?",
                confidence=0.9,
            ),
            TranscriptionSegment(
                start_time=3.0,
                end_time=7.0,
                speaker="Customer",
                text="I need help with my bill.",
                confidence=0.9,
            ),
        ],
    )


def _summary() -> SummaryResult:
    return SummaryResult(
        call_id="call-qa-1",
        call_purpose="Billing help",
        key_discussion_points=["Billing issue", "Account review", "Next steps"],
        resolution_status=ResolutionStatus.UNRESOLVED,
        sentiment_trajectory="neutral",
    )


def _config(retries=3):
    return MagicMock(
        llm_provider="openai",
        llm_model=None,
        llm_timeout_seconds=30,
        max_retries_per_node=retries,
    )


def test_score_qa_propagates_call_id_and_computes_weighted_score(monkeypatch):
    fake_result = QAScoreResult(
        call_id="wrong-id",
        dimension_scores=[
            QADimensionScore(dimension="professionalism", score=5, justification="polite"),
            QADimensionScore(dimension="empathy", score=4, justification="empathetic"),
            QADimensionScore(dimension="problem_resolution", score=3, justification="partial"),
            QADimensionScore(dimension="compliance", score=2, justification="missed step"),
            QADimensionScore(dimension="communication_clarity", score=1, justification="unclear"),
        ],
        overall_score=1.0,
    )
    structured = MagicMock()
    structured.invoke.return_value = fake_result
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    monkeypatch.setattr("src.agents.qa_scoring.load_config", lambda: _config())
    monkeypatch.setattr("src.agents.qa_scoring.get_llm", lambda **_: llm)

    result = score_qa(_transcript(), _summary())

    assert result.call_id == "call-qa-1"
    assert result.overall_score == pytest.approx(3.0)
    message = structured.invoke.call_args.args[0][1].content
    assert "[00:00-00:03] Agent: Hello, how can I help?" in message
    assert "Billing help" in message
    system = structured.invoke.call_args.args[0][0].content
    assert "Review the entire conversation" in system
    assert "supporting evidence and counterevidence" in system
    assert "requesting details as completed verification" in system
    assert "Do not manufacture a criticism" in system


def test_score_qa_retries_then_returns_result(monkeypatch):
    fake_result = QAScoreResult(
        call_id="wrong-id",
        dimension_scores=[
            QADimensionScore(dimension=name, score=3, justification="evidence")
            for name in (
                "professionalism",
                "empathy",
                "problem_resolution",
                "compliance",
                "communication_clarity",
            )
        ],
        overall_score=1.0,
    )
    structured = MagicMock()
    structured.invoke.side_effect = [RuntimeError("temporary"), fake_result]
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    monkeypatch.setattr("src.agents.qa_scoring.load_config", lambda: _config(retries=2))
    monkeypatch.setattr("src.agents.qa_scoring.get_llm", lambda **_: llm)
    monkeypatch.setattr("src.agents.qa_scoring.time.sleep", lambda _: None)

    result = score_qa(_transcript(), _summary())

    assert result.call_id == "call-qa-1"
    assert structured.invoke.call_count == 2
    assert result.overall_score == pytest.approx(3.0)


def test_score_qa_exhausted_retries_raise_domain_error(monkeypatch):
    structured = MagicMock()
    structured.invoke.side_effect = RuntimeError("provider unavailable")
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    monkeypatch.setattr("src.agents.qa_scoring.load_config", lambda: _config(retries=2))
    monkeypatch.setattr("src.agents.qa_scoring.get_llm", lambda **_: llm)
    monkeypatch.setattr("src.agents.qa_scoring.time.sleep", lambda _: None)

    with pytest.raises(QAScoringError, match="Failed to score call QA"):
        score_qa(_transcript(), _summary())

    assert structured.invoke.call_count == 2
