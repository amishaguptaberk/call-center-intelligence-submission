from pathlib import Path

import pytest

from src.services.observability import _details
from src.services.pipeline import PipelineResult, _audio_path, process_call
from src.ui.app import _load_sample, _run, build_app
from src.ui.debug_transcription import DEFAULT_SAMPLES_DIR
from tests.integration import test_reviewer_journeys

analysis = test_reviewer_journeys.analysis
database = test_reviewer_journeys.database
recording = test_reviewer_journeys.recording


def test_process_call_requires_audio():
    result = process_call(None)

    assert result == PipelineResult(
        ok=False,
        status_md="### Analysis needs attention\nAdd a call recording before starting the analysis.",
    )


def test_audio_path_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.wav"

    try:
        _audio_path(missing)
    except ValueError as exc:
        assert "no longer available" in str(exc)
    else:
        raise AssertionError("missing audio must be rejected")


def test_gradio_app_builds():
    assert build_app().__class__.__name__ == "Blocks"


@pytest.mark.skipif(
    not (DEFAULT_SAMPLES_DIR / "sample_01.mp3").exists(),
    reason="Sample audio files not bundled in this environment",
)
def test_bundled_sample_can_be_loaded():
    path = _load_sample("sample_01")

    assert path is not None
    assert Path(path).name == "sample_01.mp3"


def test_audit_details_describe_missing_values():
    assert _details('{"duration": null}') == "duration: not available"


def test_unsupported_recording_clears_results(tmp_path, database):
    audio = tmp_path / "recording.ogg"
    audio.write_bytes(b"OggS unsupported recording")
    values = _run(str(audio), "", "")
    assert "Unsupported audio format" in values[0]
    assert values[-1]["visible"] is False
    assert values[5:7] == (None, None)


def test_wav_bytes_with_bin_filename_complete_analysis(tmp_path, database, recording, analysis):
    audio = recording.rename(tmp_path / "call.bin")
    _, summary, qa = analysis
    values = _run(str(audio), "", "")
    assert "Analysis complete" in values[0]
    assert values[-1]["visible"] is True
    summary.assert_called_once()
    qa.assert_called_once()


def test_unsupported_bytes_with_wav_filename_block_analysis(tmp_path, database, analysis):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"OggS unsupported recording")
    _, summary, qa = analysis
    values = _run(str(audio), "", "")
    assert "Unsupported audio format" in values[0]
    assert values[-1]["visible"] is False
    assert values[5:7] == (None, None)
    summary.assert_not_called()
    qa.assert_not_called()


def test_successful_review_exposes_transcript_and_downloads(monkeypatch, tmp_path):
    from src.graph.state import TranscriptionSegment
    from src.services.report_generator import build_report
    from tests.unit.test_graph_event_logging import (
        _intake,
        _qa,
        _summary,
        _transcription,
    )

    report = build_report(
        intake=_intake(),
        transcription=_transcription(),
        summary=_summary(),
        qa_scores=_qa(),
    )
    report.transcription.segments = [
        TranscriptionSegment(
            start_time=0,
            end_time=2,
            text="How can I help?",
            speaker="Agent",
            confidence=0.95,
        )
    ]
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"mock audio")
    monkeypatch.setattr(
        "src.graph.workflow.run_graph",
        lambda _: {"status": "completed", "report": report},
    )
    values = _run(str(audio), "caller", "support")
    assert "Analysis complete" in values[0]
    assert values[2] and values[3] and values[4]
    assert Path(values[5]).read_bytes().startswith(b"%PDF-")
    assert '"call_id"' in Path(values[6]).read_text()
    export_name = f"CallReview_{report.created_at:%Y-%m-%d_%H-%M-%S}_{report.call_id[:8]}_"
    assert Path(values[5]).name.startswith(export_name)
    assert Path(values[5]).suffix == ".pdf"
    assert Path(values[6]).name.startswith(export_name)
    assert Path(values[6]).suffix == ".json"
    assert values[-1]["visible"] is True
