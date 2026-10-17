"""Milestone 2 contracts: boundaries and nested report serialization."""

import pytest
from pydantic import ValidationError

from src.graph.state import (
    ActionItem,
    AudioInput,
    AudioProperties,
    CallReport,
    ComplianceFlag,
    Entity,
    IntakeResult,
    PIIScanResult,
    PipelineState,
    QADimensionScore,
    QAScoreResult,
    ResolutionStatus,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)


@pytest.mark.parametrize("confidence", [0.0, 1.0])
def test_confidence_boundaries(confidence):
    assert (
        TranscriptionSegment(
            start_time=0,
            end_time=1,
            text="Hello",
            speaker="Agent",
            confidence=confidence,
        ).confidence
        == confidence
    )


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan")])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises(ValidationError):
        TranscriptionSegment(
            start_time=0,
            end_time=1,
            text="Hello",
            speaker="Agent",
            confidence=confidence,
        )


@pytest.mark.parametrize("score", [1, 5])
def test_dimension_score_boundaries(score):
    assert (
        QADimensionScore(dimension="empathy", score=score, justification="Evidence").score == score
    )


@pytest.mark.parametrize("score", [0, 6, 2.5])
def test_invalid_dimension_score_is_rejected(score):
    with pytest.raises(ValidationError):
        QADimensionScore(dimension="empathy", score=score, justification="Evidence")


def test_dimension_schema_exposes_only_canonical_names():
    assert set(QADimensionScore.model_json_schema()["properties"]["dimension"]["enum"]) == {
        "professionalism",
        "empathy",
        "problem_resolution",
        "compliance",
        "communication_clarity",
    }
    with pytest.raises(ValidationError):
        QADimensionScore(dimension="Empathy", score=3, justification="Evidence")


def _dimensions():
    return [
        QADimensionScore(dimension=name, score=3, justification="00:00 Evidence")
        for name in (
            "professionalism",
            "empathy",
            "problem_resolution",
            "compliance",
            "communication_clarity",
        )
    ]


@pytest.mark.parametrize("score", [1.0, 5.0])
def test_overall_score_boundaries(score):
    assert (
        QAScoreResult(
            call_id="call", dimension_scores=_dimensions(), overall_score=score
        ).overall_score
        == score
    )


@pytest.mark.parametrize("score", [0.99, 5.01, float("nan")])
def test_invalid_overall_score_is_rejected(score):
    with pytest.raises(ValidationError):
        QAScoreResult(call_id="call", dimension_scores=_dimensions(), overall_score=score)


def test_optional_input_metadata():
    audio = AudioInput(audio_data=b"audio", filename="call.wav")
    assert audio.caller_id is None and audio.department is None
    assert AudioInput(audio_data=b"audio", filename="call.wav", timestamp=None).timestamp is None


def test_nested_report_round_trip_and_enum_contract():
    call_id = "call-123"
    intake = IntakeResult(
        call_id=call_id,
        validation_passed=True,
        audio_properties=AudioProperties(duration_seconds=1, sample_rate=16000, channels=1),
        pii_scan=PIIScanResult(pii_detected=True, affected_fields=["caller_id"]),
        temp_file_path="/tmp/call.wav",
    )
    transcript = TranscriptionResult(
        call_id=call_id,
        full_text="Hello",
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=0, end_time=1, text="Hello", speaker="Agent", confidence=0.9
            )
        ],
    )
    summary = SummaryResult(
        call_id=call_id,
        call_purpose="Support",
        key_discussion_points=["First", "Second", "Third"],
        action_items=[ActionItem(description="Follow up", owner="Agent")],
        resolution_status="resolved",
        sentiment_trajectory="neutral",
        entities=[Entity(name="Subscription", type="product")],
    )
    qa = QAScoreResult(
        call_id=call_id,
        dimension_scores=_dimensions(),
        overall_score=3,
        compliance_flags=[
            ComplianceFlag(
                description="Missing disclosure",
                severity="high",
                timestamp_reference="00:00",
            )
        ],
    )
    report = CallReport(
        call_id=call_id,
        intake=intake,
        transcription=transcript,
        summary=summary,
        qa_scores=qa,
    )
    assert CallReport.model_validate_json(report.model_dump_json()) == report
    assert summary.resolution_status is ResolutionStatus.RESOLVED
    assert {v.value for v in ResolutionStatus} == {
        "resolved",
        "unresolved",
        "escalated",
    }
    assert report.summary.action_items[0].deadline is None


def test_pipeline_state_allows_partial_updates():
    required = {
        "audio_input",
        "intake",
        "transcription",
        "summary",
        "qa_scores",
        "report",
        "error",
        "status",
    }
    assert PipelineState.__total__ is False
    assert not PipelineState.__required_keys__
    assert required <= PipelineState.__optional_keys__
