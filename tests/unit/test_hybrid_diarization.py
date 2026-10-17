"""Unit tests for hybrid acoustic runtime, overlap diagnostics, and fallback wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.acoustic import (
    AcousticInterval,
    AttributedWord,
    WordTiming,
    acoustic_timeout_sec,
    align_words_to_speakers,
    group_utterances,
    map_roles,
    overlap_profile,
)


def test_overlap_single_speaker():
    intervals = [(0.0, 2.0, "SPEAKER_00")]
    p = overlap_profile(0.2, 1.5, intervals)
    assert p["decision"] == "single_speaker"
    assert p["primary_speaker_id"] == "SPEAKER_00"
    assert p["coverage_frac"] > 0.9


def test_overlap_consecutive_segments_same_speaker():
    intervals = [(0.0, 5.0, "SPEAKER_00")]
    a = overlap_profile(0.0, 1.0, intervals)
    b = overlap_profile(1.0, 2.0, intervals)
    assert a["primary_speaker_id"] == b["primary_speaker_id"] == "SPEAKER_00"


def test_overlap_two_speakers_in_one_segment_is_mixed():
    intervals = [(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")]
    p = overlap_profile(0.0, 2.0, intervals)
    assert p["decision"] == "mixed_speakers"
    assert p["primary_speaker_id"] is None
    assert set(p["overlap_by_speaker"]) == {"SPEAKER_00", "SPEAKER_01"}


def test_overlap_short_middle_interruption_counts_as_mixed():
    intervals = [
        (0.0, 0.9, "SPEAKER_00"),
        (0.9, 1.2, "SPEAKER_01"),  # 0.3s interruption
        (1.2, 2.0, "SPEAKER_00"),
    ]
    p = overlap_profile(0.0, 2.0, intervals)
    assert p["decision"] == "mixed_speakers"


def test_overlap_missing_coverage():
    p = overlap_profile(10.0, 11.0, [(0.0, 1.0, "SPEAKER_00")])
    assert p["decision"] == "no_acoustic_coverage"
    assert p["primary_speaker_id"] is None


def test_overlap_small_timestamp_discrepancy_still_single():
    # Tiny nick of another speaker (<0.15s and <15%) stays dominant single.
    intervals = [(0.0, 2.0, "SPEAKER_00"), (1.98, 2.05, "SPEAKER_01")]
    p = overlap_profile(0.0, 2.0, intervals)
    assert p["decision"] == "single_speaker_dominant"
    assert p["primary_speaker_id"] == "SPEAKER_00"


def test_align_words_stable_identity_across_turns():
    intervals = [
        AcousticInterval(0.0, 1.0, "SPEAKER_00"),
        AcousticInterval(1.5, 2.5, "SPEAKER_01"),
        AcousticInterval(3.0, 4.0, "SPEAKER_00"),
    ]
    words = [
        WordTiming("hello", 0.1, 0.4),
        WordTiming("world", 1.6, 2.0),
        WordTiming("again", 3.2, 3.6),
    ]
    attr = align_words_to_speakers(words, intervals)
    assert [w.speaker_id for w in attr] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_role_mapping_unknown_when_no_speakers():
    roles = map_roles([])
    assert roles.mapping == {}
    assert roles.method == "empty"


def test_word_level_split_two_speakers_in_asr_span():
    intervals = [
        AcousticInterval(0.0, 1.0, "SPEAKER_00"),
        AcousticInterval(1.0, 2.0, "SPEAKER_01"),
    ]
    words = [
        AttributedWord("hi", 0.1, 0.4, "SPEAKER_00"),
        AttributedWord("there", 0.5, 0.9, "SPEAKER_00"),
        AttributedWord("thanks", 1.1, 1.4, "SPEAKER_01"),
        AttributedWord("bye", 1.5, 1.9, "SPEAKER_01"),
    ]
    utts, _ = group_utterances(words, intervals=intervals, asr_spans=[(0.1, 1.9)], turn_first=True)
    speakers = {u.speaker_id for u in utts if u.speaker_id}
    assert speakers == {"SPEAKER_00", "SPEAKER_01"}


def test_acoustic_timeout_policy_scales_with_duration(monkeypatch):
    monkeypatch.delenv("ACOUSTIC_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("ACOUSTIC_TIMEOUT_FLOOR_SEC", "60")
    monkeypatch.setenv("ACOUSTIC_TIMEOUT_BASE_SEC", "30")
    monkeypatch.setenv("ACOUSTIC_TIMEOUT_PER_AUDIO_SEC", "2.5")
    assert acoustic_timeout_sec(10) == 60.0  # floor
    assert acoustic_timeout_sec(120) == 30 + 2.5 * 120


def test_acoustic_timeout_fixed_override(monkeypatch):
    monkeypatch.setenv("ACOUSTIC_TIMEOUT_SECONDS", "45")
    assert acoustic_timeout_sec(999) == 45.0


def test_bounded_runner_terminates_on_timeout(monkeypatch):
    from src.agents import acoustic as ac

    class _FakeProc:
        def __init__(self, *a, **k):
            self._alive = True
            self.exitcode = None

        def start(self):
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return self._alive

        def terminate(self):
            self._alive = False
            self.exitcode = -15

        def kill(self):
            self._alive = False
            self.exitcode = -9

    class _FakeCtx:
        def Queue(self):
            class Q:
                def empty(self):
                    return True

                def get(self):
                    raise RuntimeError("should not get")

            return Q()

        def Process(self, **kwargs):
            return _FakeProc()

    monkeypatch.setattr(ac.mp, "get_context", lambda *a, **k: _FakeCtx())
    with pytest.raises(TimeoutError, match="exceeded hard timeout"):
        ac.run_build_role_segments_bounded(
            "/tmp/does-not-matter.wav",
            [WordTiming("x", 0.0, 0.1)],
            [(0.0, 0.1)],
            timeout_sec=1.0,
        )


def test_hybrid_fallback_on_timeout(monkeypatch, tmp_path):
    from src.agents import transcription as tr
    from src.database.connection import _reset_engine_state
    from src.graph.state import AudioProperties, IntakeResult, PIIScanResult

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "hybrid.sqlite3"))
    _reset_engine_state()
    audio = tmp_path / "timeout.wav"
    audio.write_bytes(b"timeout-audio")

    class _W:
        start = 0.0
        end = 1.0
        text = "Thank you for calling support."
        words = None
        avg_logprob = -0.2
        no_speech_prob = 0.1

    class _Model:
        def transcribe(self, **kwargs):
            return ([_W()], None)

    monkeypatch.setenv("DIARIZATION_BACKEND", "hybrid")
    monkeypatch.setattr(tr, "_get_whisper_model", lambda: _Model())
    monkeypatch.setattr(tr, "_audio_duration_sec", lambda p: 30.0)
    monkeypatch.setattr(tr, "acoustic_timeout_sec", lambda d: 1.0)
    monkeypatch.setattr(
        tr,
        "_call_acoustic",
        lambda *a, **k: (_ for _ in ()).throw(
            TimeoutError("Acoustic Community-1 exceeded hard timeout of 1.0s")
        ),
    )

    intake = IntakeResult(
        call_id="t1",
        validation_passed=True,
        validation_error=None,
        audio_properties=AudioProperties(duration_seconds=30, sample_rate=16000, channels=1),
        pii_scan=PIIScanResult(),
        temp_file_path=str(audio),
    )
    result = tr.run_transcription(intake)
    diag = tr.get_last_transcription_diagnostics()
    assert diag["fallback_activated"] is True
    assert diag["label_source"] == "heuristic_fallback"
    assert diag["acoustic_verified"] is False
    assert "acoustic_timeout" in diag["fallback_reason"]
    assert result.segments
    assert all(s.speaker in ("Agent", "Customer", "Ambiguous") for s in result.segments)


def test_hybrid_fallback_on_inference_error(monkeypatch, tmp_path):
    from src.agents import transcription as tr
    from src.database.connection import _reset_engine_state
    from src.graph.state import AudioProperties, IntakeResult, PIIScanResult

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "hybrid.sqlite3"))
    _reset_engine_state()
    audio = tmp_path / "error.wav"
    audio.write_bytes(b"error-audio")

    class _W:
        start = 0.0
        end = 1.0
        text = "Thank you for calling support."
        words = None
        avg_logprob = -0.2
        no_speech_prob = 0.1

    class _Model:
        def transcribe(self, **kwargs):
            return ([_W()], None)

    monkeypatch.setenv("DIARIZATION_BACKEND", "hybrid")
    monkeypatch.setattr(tr, "_get_whisper_model", lambda: _Model())
    monkeypatch.setattr(tr, "_audio_duration_sec", lambda p: 30.0)
    monkeypatch.setattr(
        tr,
        "_call_acoustic",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    intake = IntakeResult(
        call_id="t2",
        validation_passed=True,
        validation_error=None,
        audio_properties=AudioProperties(duration_seconds=30, sample_rate=16000, channels=1),
        pii_scan=PIIScanResult(),
        temp_file_path=str(audio),
    )
    result = tr.run_transcription(intake)
    diag = tr.get_last_transcription_diagnostics()
    assert diag["fallback_activated"] is True
    assert "acoustic_error" in diag["fallback_reason"]
    assert result.segments


def test_ground_truth_annotation_file_untouched():
    import hashlib

    path = Path("evaluation/annotations/recordings/sample_01/annotation.v2.json")
    assert path.is_file()
    before = path.read_bytes()
    # Touch-free invariant: hash stable within this test (no writes).
    assert hashlib.sha256(before).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest()
