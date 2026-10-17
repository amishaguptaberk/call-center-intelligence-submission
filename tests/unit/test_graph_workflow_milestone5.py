import json

import pytest
from sqlalchemy import select

from src.database import connection
from src.database.models import AuditLogEntry
from src.database.repository import get_call_analysis
from src.graph import nodes
from src.graph.state import AudioInput, InjectionScanResult
from src.graph.workflow import run_graph
from tests.unit.test_graph_event_logging import _intake, _qa, _summary, _transcription


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "milestone5.sqlite3"))
    connection._reset_engine_state()
    connection.init_db()
    yield
    connection._reset_engine_state()


@pytest.fixture
def mocked_pipeline(monkeypatch):
    monkeypatch.setattr(nodes, "run_intake", lambda _audio: _intake())
    monkeypatch.setattr(nodes, "run_transcription", lambda _intake_result: _transcription())
    monkeypatch.setattr(nodes, "detect_injection", lambda _text: InjectionScanResult())
    monkeypatch.setattr(nodes, "summarize", lambda _transcript: _summary())
    monkeypatch.setattr(nodes, "score_qa", lambda transcript, summary: _qa())


def test_compiled_workflow_persists_report_and_audit_events(database, mocked_pipeline):
    result = run_graph(_state())

    analysis = get_call_analysis("call-1")
    events = _events()

    assert result["report"].call_id == "call-1"
    assert analysis is not None
    assert json.loads(analysis.report_json)["call_id"] == "call-1"
    assert [event.action for event in events] == ["started", "completed"]
    assert json.loads(events[-1].details)["stage"] == "report"


def test_compiled_workflow_persists_flagged_review_report(database, mocked_pipeline, monkeypatch):
    monkeypatch.setattr(nodes, "score_qa", lambda transcript, summary: _qa(critical=True))

    result = run_graph(_state())

    analysis = get_call_analysis("call-1")
    events = _events()

    assert result["status"] == "supervisor_review"
    assert result["report"].call_id == "call-1"
    assert analysis is not None
    assert [event.action for event in events] == ["started", "flagged_for_review"]


def test_compiled_workflow_invalid_audio_fails_and_logs(database, monkeypatch):
    monkeypatch.setattr(nodes, "run_intake", lambda _audio: _intake(validation_error="bad audio"))

    result = run_graph(_state())

    events = _events()

    assert result["status"] == "failed"
    assert "report" not in result
    assert get_call_analysis("call-1") is None
    assert [event.action for event in events] == ["started", "failed"]
    assert json.loads(events[-1].details)["validation_error"] == "bad audio"


def test_compiled_workflow_injection_fails_and_logs(database, mocked_pipeline, monkeypatch):
    monkeypatch.setattr(
        nodes,
        "detect_injection",
        lambda _text: InjectionScanResult(
            injection_detected=True,
            matched_patterns=["ignore_previous"],
        ),
    )

    result = run_graph(_state())

    events = _events()

    assert result["status"] == "failed"
    assert get_call_analysis("call-1") is None
    assert [event.action for event in events] == ["started", "failed"]
    assert json.loads(events[-1].details)["matched_patterns"] == ["ignore_previous"]


def test_run_graph_converts_unexpected_exception_to_failed_state(
    database, mocked_pipeline, monkeypatch
):
    def fail(_intake_result):
        raise RuntimeError("transcriber unavailable")

    monkeypatch.setattr(nodes, "run_transcription", fail)

    result = run_graph(_state())

    events = _events()

    assert result["status"] == "failed"
    assert result["error"] == "transcription failed (RuntimeError). Please retry the analysis."
    assert [event.action for event in events] == ["started", "failed"]
    assert json.loads(events[-1].details)["error"] == result["error"]


def _state():
    return {"audio_input": AudioInput(audio_data=b"RIFF", filename="call.wav")}


def _events():
    with connection.session_scope() as session:
        rows = session.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)).all()
        for row in rows:
            session.expunge(row)
        return rows
