from types import SimpleNamespace

import pytest

from src.database import connection
from src.graph import nodes
from src.graph.state import (
    AudioInput,
    AudioProperties,
    ComplianceFlag,
    InjectionScanResult,
    IntakeResult,
    PIIScanResult,
    QADimensionScore,
    QAScoreResult,
    ResolutionStatus,
    SummaryResult,
    TranscriptionResult,
)


class FakeEventLogger:
    def __init__(self):
        self.events = []

    def log(self, call_id, action, user, details=None, stage=None):
        self.events.append((call_id, action, user, details, stage))


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "events.sqlite3"))
    connection._reset_engine_state()
    connection.init_db()
    yield
    connection._reset_engine_state()


def test_intake_logs_started(monkeypatch):
    logger = FakeEventLogger()
    intake = _intake()
    monkeypatch.setattr(nodes, "event_logger", logger)
    monkeypatch.setattr(nodes, "run_intake", lambda _audio: intake)

    result = nodes.intake_node({"audio_input": AudioInput(audio_data=b"RIFF", filename="call.wav")})

    assert result == {"intake": intake}
    assert logger.events == [
        (
            "call-1",
            "started",
            "system",
            {"filename": "call.wav", "validation_passed": True},
            "intake",
        )
    ]


def test_terminal_nodes_log_lifecycle_events(monkeypatch):
    logger = FakeEventLogger()
    monkeypatch.setattr(nodes, "event_logger", logger)
    monkeypatch.setattr(
        nodes,
        "build_report",
        lambda **kwargs: SimpleNamespace(
            call_id="call-1",
            qa_scores=SimpleNamespace(overall_score=4.2, compliance_flags=[object()]),
        ),
    )

    base = {
        "intake": _intake(),
        "sanitized_transcription": _transcription(),
        "summary": _summary(),
        "qa_scores": _qa(),
    }

    assert nodes.report_node(base)["report"].call_id == "call-1"
    review = nodes.supervisor_review_node({**base, "qa_scores": _qa(critical=True)})
    assert review["status"] == "supervisor_review"
    assert review["report"].call_id == "call-1"
    assert nodes.error_node(
        {
            "intake": _intake(validation_error="bad audio"),
            "injection_scan": InjectionScanResult(
                injection_detected=True, matched_patterns=["ignore_previous"]
            ),
        }
    ) == {"status": "failed"}

    assert logger.events == [
        (
            "call-1",
            "completed",
            "system",
            {"overall_score": 4.2, "compliance_flags": 1},
            "report",
        ),
        (
            "call-1",
            "flagged_for_review",
            "system",
            {"critical_flags": ["Missing disclosure"]},
            "qa",
        ),
        (
            "call-1",
            "failed",
            "system",
            {
                "validation_error": "bad audio",
                "matched_patterns": ["ignore_previous"],
            },
            "error",
        ),
    ]


def test_audit_logger_records_stage_in_details(database):
    import json

    from sqlalchemy import select

    from src.database import connection
    from src.database.models import AuditLogEntry
    from src.security.audit import AuditLogger

    AuditLogger().log("call-1", "completed", "system", stage="report")

    with connection.session_scope() as session:
        row = session.scalar(select(AuditLogEntry))
        assert json.loads(row.details) == {"stage": "report"}


def _intake(validation_error=None):
    return IntakeResult(
        call_id="call-1",
        validation_passed=validation_error is None,
        validation_error=validation_error,
        audio_properties=AudioProperties(duration_seconds=1.0, sample_rate=16000, channels=1),
        pii_scan=PIIScanResult(),
    )


def _transcription():
    return TranscriptionResult(call_id="call-1", full_text="Hello", segments=[], language="en")


def _summary():
    return SummaryResult(
        call_id="call-1",
        call_purpose="Support",
        key_discussion_points=["one", "two", "three"],
        resolution_status=ResolutionStatus.RESOLVED,
        sentiment_trajectory="neutral",
    )


def _qa(critical=False):
    return QAScoreResult(
        call_id="call-1",
        dimension_scores=[
            QADimensionScore(dimension="professionalism", score=4, justification="ok"),
            QADimensionScore(dimension="empathy", score=4, justification="ok"),
            QADimensionScore(dimension="problem_resolution", score=4, justification="ok"),
            QADimensionScore(dimension="compliance", score=4, justification="ok"),
            QADimensionScore(dimension="communication_clarity", score=4, justification="ok"),
        ],
        overall_score=4.0,
        compliance_flags=[
            ComplianceFlag(
                description="Missing disclosure",
                severity="critical",
                timestamp_reference="00:10",
            )
        ]
        if critical
        else [],
    )
