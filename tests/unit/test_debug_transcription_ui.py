"""Unit tests for Milestone 3 Slice 1 local Gradio debug helpers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

from src.graph.state import (
    AudioProperties,
    IntakeResult,
    PIIScanResult,
    TranscriptionResult,
    TranscriptionSegment,
)
from src.ui.debug_transcription import (
    count_flagged,
    extract_flagged_records,
    format_timestamp,
    list_sample_names,
    load_flagged_indices,
    process_uploaded_audio,
    resolve_sample_path,
    save_flags,
    segments_as_rows,
    toggle_flag_at,
)


def _segment(**kwargs) -> TranscriptionSegment:
    defaults = dict(
        start_time=65.5,
        end_time=68.25,
        text="  hello there  ",
        speaker="Agent",
        confidence=0.91,
    )
    defaults.update(kwargs)
    return TranscriptionSegment(**defaults)


def _transcription() -> TranscriptionResult:
    return TranscriptionResult(
        call_id="call-1",
        full_text="hello there thanks",
        language="en",
        segments=[
            _segment(),
            _segment(
                start_time=68.25,
                end_time=70.0,
                text="thanks",
                speaker="Customer",
                confidence=0.42,
            ),
        ],
    )


def test_format_timestamp():
    assert format_timestamp(0) == "00:00.00"
    assert format_timestamp(65.5) == "01:05.50"
    assert format_timestamp(68.25) == "01:08.25"


def test_format_transcript_text_includes_wait_summary():
    from src.ui.debug_transcription import format_transcript_text

    text = format_transcript_text(_transcription())
    assert "Wait:" in text
    assert "Call starts" in text or "In-call window" in text
    assert "Agent" in text
    assert "Customer" in text


def test_format_transcript_text_inserts_hold_row():
    from src.ui.debug_transcription import format_transcript_text

    result = TranscriptionResult(
        call_id="c1",
        full_text="one two",
        language="en",
        segments=[
            _segment(
                start_time=0.0,
                end_time=1.0,
                text="Thank you for calling support. How may I help you?",
                speaker="Agent",
            ),
            _segment(
                start_time=12.0,
                end_time=13.0,
                text="Thanks",
                speaker="Customer",
                confidence=0.9,
            ),
        ],
    )
    text = format_transcript_text(result)
    assert "Hold" in text
    assert "[hold 11.0s]" in text
    assert "in-call" in text.lower() or "Call:" in text


def test_segments_as_rows_are_inspectable():
    rows = segments_as_rows(_transcription())
    assert rows == [
        [0, False, "01:05.50", "01:08.25", "Agent", "0.91", "hello there"],
        [1, False, "01:08.25", "01:10.00", "Customer", "0.42", "thanks"],
    ]
    flagged = segments_as_rows(_transcription(), flagged_indices={1})
    assert flagged[1][1] is True


def test_toggle_and_save_flags_omit_transcript_text(tmp_path):
    rows = segments_as_rows(_transcription())
    rows = toggle_flag_at(rows, 0)
    assert count_flagged(rows) == 1
    path = save_flags("sample_01", "heuristic", rows, flags_dir=tmp_path)
    payload = path.read_text(encoding="utf-8")
    assert "hello there" not in payload
    assert "thanks" not in payload
    assert load_flagged_indices("sample_01", "heuristic", flags_dir=tmp_path) == {0}
    records = extract_flagged_records(rows)
    assert records == [
        {
            "row_id": 0,
            "start": "01:05.50",
            "end": "01:08.25",
            "predicted_speaker": "Agent",
            "confidence": "0.91",
        }
    ]


def test_process_uploaded_audio_success(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake-wav-bytes")

    intake = IntakeResult(
        call_id="c1",
        validation_passed=True,
        audio_properties=AudioProperties(duration_seconds=1.0, sample_rate=8000, channels=1),
        pii_scan=PIIScanResult(),
        temp_file_path=str(audio),
    )
    result = _transcription()

    monkeypatch.setattr(
        "src.ui.debug_transcription.run_intake",
        MagicMock(return_value=intake),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_transcription",
        MagicMock(return_value=result),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.get_last_transcription_diagnostics",
        MagicMock(
            return_value={
                "backend": "heuristic",
                "label_source": "heuristic",
                "cache_hit": False,
                "timing_sec": {"total_run_transcription": 2.0},
            }
        ),
    )

    view = process_uploaded_audio(str(audio))
    assert view.ok is True
    assert "2 in-call" in view.status.lower()
    assert "label_source=heuristic" in view.status
    assert "cache hit" not in view.status
    assert view.audio_path is not None
    assert len(view.segment_rows) == 2
    assert "Agent" in view.transcript_text
    assert "Customer" in view.transcript_text
    # status must not dump raw transcript body
    assert "hello there" not in view.status
    assert "thanks" not in view.status


def test_process_uploaded_audio_status_uses_diagnostics_label_source(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake")
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_intake",
        MagicMock(
            return_value=IntakeResult(
                call_id="c1",
                validation_passed=True,
                audio_properties=AudioProperties(
                    duration_seconds=1.0, sample_rate=8000, channels=1
                ),
                pii_scan=PIIScanResult(),
                temp_file_path=str(audio),
            )
        ),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_transcription",
        MagicMock(return_value=_transcription()),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.get_last_transcription_diagnostics",
        MagicMock(
            return_value={
                "backend": "hybrid",
                "label_source": "heuristic_fallback",
                "cache_hit": False,
                "timing_sec": {"total_run_transcription": 12.0},
            }
        ),
    )

    view = process_uploaded_audio(str(audio), backend="hybrid")
    assert view.ok is True
    assert "requested=hybrid" in view.status
    assert "label_source=heuristic_fallback" in view.status
    assert "cache hit" not in view.status


def test_process_uploaded_audio_sets_backend_for_request(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake")
    seen: list[str | None] = []

    def _fake_intake(_audio_input):
        seen.append(os.environ.get("DIARIZATION_BACKEND"))
        return IntakeResult(
            call_id="c1",
            validation_passed=True,
            audio_properties=AudioProperties(duration_seconds=1.0, sample_rate=8000, channels=1),
            pii_scan=PIIScanResult(),
            temp_file_path=str(audio),
        )

    monkeypatch.setenv("DIARIZATION_BACKEND", "acoustic")
    monkeypatch.setattr("src.ui.debug_transcription.run_intake", _fake_intake)
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_transcription",
        MagicMock(return_value=_transcription()),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.get_last_transcription_diagnostics",
        MagicMock(return_value={"timing_sec": {"total_run_transcription": 0.1}}),
    )

    view = process_uploaded_audio(str(audio), backend="heuristic")
    assert view.ok is True
    assert seen == ["heuristic"]
    assert os.environ.get("DIARIZATION_BACKEND") == "acoustic"


def test_process_uploaded_audio_rejects_missing_path():
    view = process_uploaded_audio(None)
    assert view.ok is False
    assert view.audio_path is None
    assert view.segment_rows == []
    assert "upload" in view.status.lower() or "audio" in view.status.lower()


def test_process_uploaded_audio_intake_failure(tmp_path, monkeypatch):
    audio = tmp_path / "bad.wav"
    audio.write_bytes(b"x")
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_intake",
        MagicMock(
            return_value=IntakeResult(
                call_id="c1",
                validation_passed=False,
                validation_error="unsupported format",
                audio_properties=AudioProperties(duration_seconds=0.0, sample_rate=0, channels=0),
                pii_scan=PIIScanResult(),
                temp_file_path=None,
            )
        ),
    )
    transcribe = MagicMock()
    monkeypatch.setattr("src.ui.debug_transcription.run_transcription", transcribe)

    view = process_uploaded_audio(str(audio))
    assert view.ok is False
    assert "unsupported format" in view.status
    assert view.segment_rows == []
    transcribe.assert_not_called()


def test_process_uploaded_audio_transcription_error(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake")
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_intake",
        MagicMock(
            return_value=IntakeResult(
                call_id="c1",
                validation_passed=True,
                audio_properties=AudioProperties(
                    duration_seconds=1.0, sample_rate=8000, channels=1
                ),
                pii_scan=PIIScanResult(),
                temp_file_path=str(audio),
            )
        ),
    )
    monkeypatch.setattr(
        "src.ui.debug_transcription.run_transcription",
        MagicMock(side_effect=ValueError("cannot transcribe invalid audio")),
    )

    view = process_uploaded_audio(str(audio))
    assert view.ok is False
    assert "cannot transcribe" in view.status.lower()
    assert view.segment_rows == []


def test_list_and_resolve_bundled_samples(tmp_path):
    for i in range(1, 11):
        (tmp_path / f"sample_{i:02d}.mp3").write_bytes(b"x")
    names = list_sample_names(tmp_path)
    assert names == [f"sample_{i:02d}" for i in range(1, 11)]
    assert resolve_sample_path("sample_03", tmp_path).endswith("sample_03.mp3")
    assert resolve_sample_path("missing", tmp_path) is None
