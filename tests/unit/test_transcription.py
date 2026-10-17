"""Unit tests for SHA-256 transcription caching (mocked Whisper)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect

from src.database.connection import _reset_engine_state, get_engine, init_db
from src.graph.state import (
    AudioProperties,
    IntakeResult,
    PIIScanResult,
    TranscriptionResult,
    TranscriptionSegment,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setenv("DIARIZATION_BACKEND", "heuristic")
    _reset_engine_state()
    init_db()
    yield
    _reset_engine_state()


def _intake(call_id: str, path: Path) -> IntakeResult:
    return IntakeResult(
        call_id=call_id,
        validation_passed=True,
        audio_properties=AudioProperties(duration_seconds=1.0, sample_rate=8000, channels=1),
        pii_scan=PIIScanResult(),
        temp_file_path=str(path),
    )


def _result(call_id: str = "call-1") -> TranscriptionResult:
    return TranscriptionResult(
        call_id=call_id,
        full_text="hello there",
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=0.0,
                end_time=1.0,
                text="hello there",
                speaker="Agent",
                confidence=0.91,
            )
        ],
    )


def test_init_db_creates_cache_table(db):
    assert "transcription_cache" in inspect(get_engine()).get_table_names()


def test_unknown_hash_is_cache_miss(db):
    from src.agents.transcription import _check_cache

    assert _check_cache("0" * 64) is None


def test_cache_survives_database_engine_restart(db):
    from src.agents.transcription import _check_cache, _save_cache

    original = _result()
    _save_cache("b" * 64, original)
    _reset_engine_state()
    init_db()
    assert _check_cache("b" * 64) == original


def test_save_and_retrieve_preserves_transcription(db):
    from src.agents.transcription import _check_cache, _save_cache

    original = _result("stored-id")
    _save_cache("a" * 64, original)
    loaded = _check_cache("a" * 64)
    assert loaded is not None
    assert loaded.call_id == "stored-id"
    assert loaded.full_text == original.full_text
    assert loaded.language == "en"
    assert loaded.segments[0].speaker == "Agent"
    assert loaded.segments[0].confidence == 0.91
    assert loaded.segments[0].text == "hello there"


def test_duplicate_hash_insert_does_not_raise(db):
    from src.agents.transcription import _save_cache

    _save_cache("b" * 64, _result("first"))
    _save_cache("b" * 64, _result("second"))


def test_identical_audio_transcribed_only_once(db, tmp_path, monkeypatch):
    from src.agents.transcription import run_transcription

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake-audio-bytes")
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], None)
    monkeypatch.setattr("src.agents.transcription._get_whisper_model", lambda: mock_model)

    first = run_transcription(_intake("call-a", audio))
    second = run_transcription(_intake("call-b", audio))

    assert mock_model.transcribe.call_count == 1
    assert first.call_id == "call-a"
    assert second.call_id == "call-b"
    assert first.full_text == second.full_text


def test_cache_hit_returns_current_call_id_without_whisper(db, tmp_path, monkeypatch):
    from src.agents.transcription import (
        _compute_audio_hash,
        _save_cache,
        get_last_transcription_diagnostics,
        run_transcription,
    )

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake-audio-bytes")
    monkeypatch.setenv("DIARIZATION_BACKEND", "heuristic")
    _save_cache(_compute_audio_hash(audio), _result("old-call"))

    mock_get = MagicMock()
    monkeypatch.setattr("src.agents.transcription._get_whisper_model", mock_get)

    hit = run_transcription(_intake("new-call", audio))
    mock_get.assert_not_called()
    assert hit.call_id == "new-call"
    assert hit.full_text == "hello there"
    assert hit.segments[0].speaker == "Agent"
    diag = get_last_transcription_diagnostics()
    assert diag is not None
    assert diag["cache_hit"] is True
    assert diag["backend"] == "heuristic"
    assert diag["label_source"] == "heuristic"


def test_cache_miss_when_diarization_backend_changes(db, tmp_path, monkeypatch):
    """Heuristic labels must not be reused for hybrid/acoustic."""
    from src.agents.transcription import run_transcription

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake-audio-bytes")
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], None)
    monkeypatch.setattr("src.agents.transcription._get_whisper_model", lambda: mock_model)

    monkeypatch.setenv("DIARIZATION_BACKEND", "heuristic")
    run_transcription(_intake("call-a", audio))
    assert mock_model.transcribe.call_count == 1

    monkeypatch.setenv("DIARIZATION_BACKEND", "hybrid")
    monkeypatch.setattr(
        "src.agents.transcription._call_acoustic",
        lambda *a, **k: (_ for _ in ()).throw(TimeoutError("skip acoustic")),
    )
    run_transcription(_intake("call-b", audio))
    assert mock_model.transcribe.call_count == 2


def test_database_errors_are_not_swallowed(db, tmp_path, monkeypatch):
    from src.agents.transcription import _check_cache, run_transcription

    def _boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("src.database.connection.get_session", _boom)

    with pytest.raises(RuntimeError, match="db down"):
        _check_cache("c" * 64)

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake-audio-bytes")
    with pytest.raises(RuntimeError, match="db down"):
        run_transcription(_intake("call-err", audio))


@pytest.mark.parametrize("cuda", [False, True])
def test_whisper_lifecycle_device_and_size(monkeypatch, cuda):
    import sys
    from types import SimpleNamespace

    from src.agents import transcription as t

    monkeypatch.setattr(t, "_model", None)
    monkeypatch.setattr(t, "_model_size", None)
    monkeypatch.setattr(t, "config", SimpleNamespace(whisper_model_size="tiny"))
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: cuda)),
    )
    factory = MagicMock()
    monkeypatch.setattr(t, "WhisperModel", factory)
    first = t._get_whisper_model()
    assert t._get_whisper_model() is first
    factory.assert_called_once_with(
        "tiny",
        device="cuda" if cuda else "cpu",
        compute_type="float16" if cuda else "int8",
    )
    monkeypatch.setattr(t, "config", SimpleNamespace(whisper_model_size="base"))
    t._get_whisper_model()
    assert factory.call_count == 2
    assert factory.call_args.args == ("base",)


def test_whisper_without_torch_uses_cpu(monkeypatch):
    import sys
    from types import SimpleNamespace

    from src.agents import transcription as t

    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setattr(t, "_model", None)
    monkeypatch.setattr(t, "_model_size", None)
    monkeypatch.setattr(t, "config", SimpleNamespace(whisper_model_size="tiny"))
    factory = MagicMock()
    monkeypatch.setattr(t, "WhisperModel", factory)
    t._get_whisper_model()
    factory.assert_called_once_with("tiny", device="cpu", compute_type="int8")


@pytest.mark.parametrize(
    "logprob,silence,expected",
    [
        (-0.2, 0.1, 0.83),
        (-2, 0, 0.3),
        (1, 0, 1),
        (-1, 1, 0),
        (-0.123456, 0.123456, 0.8765),
    ],
)
def test_segment_confidence_spec(logprob, silence, expected):
    from src.agents.transcription import _segment_confidence

    assert _segment_confidence(logprob, silence) == expected


def test_hash_reads_in_8k_chunks(tmp_path, monkeypatch):
    import hashlib
    from unittest.mock import mock_open

    from src.agents import transcription as t

    data = b"a" * 20000
    reader = mock_open(read_data=data)
    monkeypatch.setattr(t, "open", reader, raising=False)
    assert t._compute_audio_hash(tmp_path / "call.wav") == hashlib.sha256(data).hexdigest()
    assert [c.args for c in reader().read.call_args_list] == [(8192,)] * 4


def test_transcription_options_output_and_distinct_audio(db, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from src.agents import transcription as t

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"first")
    model = MagicMock()
    model.transcribe.return_value = (
        [
            SimpleNamespace(
                text="Thank you for calling.",
                start=0,
                end=1,
                avg_logprob=-0.2,
                no_speech_prob=0.1,
                words=[],
            )
        ],
        None,
    )
    monkeypatch.setattr(t, "_get_whisper_model", lambda: model)
    monkeypatch.setattr(t, "_audio_duration_sec", lambda p: 1)
    result = t.run_transcription(_intake("one", audio))
    model.transcribe.assert_called_once_with(
        audio=str(audio),
        beam_size=1,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    assert result.call_id == "one"
    assert result.segments[0].confidence == 0.83
    assert result.segments[0].speaker == "Agent"
    audio.write_bytes(b"second")
    t.run_transcription(_intake("two", audio))
    assert model.transcribe.call_count == 2


def test_failed_inference_is_not_cached(db, tmp_path, monkeypatch):
    from src.agents import transcription as t

    audio = tmp_path / "call.wav"
    audio.write_bytes(b"broken")
    model = MagicMock()
    model.transcribe.side_effect = RuntimeError("decoder failed")
    monkeypatch.setattr(t, "_get_whisper_model", lambda: model)
    with pytest.raises(RuntimeError, match="decoder failed"):
        t.run_transcription(_intake("one", audio))
    assert t._check_cache(t._compute_audio_hash(audio)) is None
    with pytest.raises(FileNotFoundError):
        t.run_transcription(_intake("missing", tmp_path / "missing.wav"))


def test_cache_survives_engine_restart_and_duplicate_preserves_first(db):
    from src.agents.transcription import _check_cache, _save_cache

    _save_cache("d" * 64, _result("first"))
    _save_cache("d" * 64, _result("second"))
    _reset_engine_state()
    assert _check_cache("d" * 64) == _result("first")


def test_invalid_intake_stops_before_database_or_model(tmp_path, monkeypatch):
    from src.agents import transcription as t

    initialize = MagicMock()
    model = MagicMock()
    monkeypatch.setattr(t, "init_db", initialize)
    monkeypatch.setattr(t, "_get_whisper_model", model)
    intake = _intake("bad", tmp_path / "missing.wav").model_copy(
        update={"validation_passed": False}
    )
    with pytest.raises(ValueError, match="invalid audio"):
        t.run_transcription(intake)
    initialize.assert_not_called()
    model.assert_not_called()
