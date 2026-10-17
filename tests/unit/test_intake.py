import tempfile
import wave
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest

from src.agents.intake import run_intake
from src.graph.state import AudioInput
from src.utils import audio as audio_utils


def _make_wav_bytes(duration_seconds: float, sample_rate: int = 8000) -> bytes:
    nframes = int(duration_seconds * sample_rate)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(b"\x00\x00" * nframes)
    return buffer.getvalue()


def test_wav_duration_checked_before_file_size(monkeypatch):
    """Overlong WAV that also exceeds size limit must fail on duration first."""
    monkeypatch.setattr(audio_utils, "MAX_DURATION_SECONDS", 1)
    monkeypatch.setattr(audio_utils, "MAX_FILE_SIZE_BYTES", 10)
    monkeypatch.setattr("src.agents.intake.MAX_DURATION_SECONDS", 1)

    validate_calls: list[object] = []

    def _tracking_validate(audio_bytes: bytes, filename: str):
        validate_calls.append((audio_bytes, filename))
        return audio_utils.validate_audio_file(audio_bytes, filename)

    monkeypatch.setattr("src.agents.intake.validate_audio_file", _tracking_validate)

    audio_bytes = _make_wav_bytes(duration_seconds=2)
    assert len(audio_bytes) > 10

    result = run_intake(AudioInput(audio_data=audio_bytes, filename="long.wav"))

    assert result.validation_passed is False
    assert result.validation_error is not None
    assert "duration" in result.validation_error.lower()
    assert "filesize" not in result.validation_error.lower()
    assert validate_calls == []


def test_overlong_wav_is_rejected(monkeypatch):
    monkeypatch.setattr("src.agents.intake.MAX_DURATION_SECONDS", 1)

    result = run_intake(
        AudioInput(
            audio_data=_make_wav_bytes(duration_seconds=2),
            filename="overlong.wav",
        )
    )

    assert result.validation_passed is False
    assert result.validation_error is not None
    assert "duration" in result.validation_error.lower()


def test_malformed_wav_fails_gracefully():
    malformed = b"RIFF\x00\x00\x00\x00WAVE" + b"not-a-valid-wav-body"

    result = run_intake(AudioInput(audio_data=malformed, filename="bad.wav"))

    assert result.validation_passed is False
    assert result.validation_error is not None
    assert result.temp_file_path is None


@pytest.mark.parametrize("remaining_bytes", [44, 60])
def test_truncated_wav_rejected_by_properties_and_intake(remaining_bytes, tmp_path):
    audio = _make_wav_bytes(1)[:remaining_bytes]
    with pytest.raises(audio_utils.AudioValidationError, match="Incomplete WAV"):
        audio_utils.extract_audio_properties(audio, "wav")
    result = run_intake(AudioInput(audio_data=audio, filename="truncated.wav"))
    assert not result.validation_passed
    assert "Incomplete WAV" in result.validation_error
    assert result.temp_file_path is None
    assert list(tmp_path.iterdir()) == []


# Keep all files created by successful intake inside pytest's temporary directory.
@pytest.fixture(autouse=True)
def isolated_intake_files(monkeypatch, tmp_path):
    original = tempfile.NamedTemporaryFile

    def create_temp_file(*args, **kwargs):
        return original(*args, **{**kwargs, "dir": tmp_path})

    monkeypatch.setattr("src.agents.intake.tempfile.NamedTemporaryFile", create_temp_file)


def test_valid_wav_preserves_audio_and_extracts_properties():
    audio = _make_wav_bytes(0.25)
    result = run_intake(AudioInput(audio_data=audio, filename="call.wav"))
    assert result.validation_passed
    assert result.validation_error is None
    assert str(UUID(result.call_id)) == result.call_id
    assert result.audio_properties.duration_seconds == pytest.approx(0.25)
    assert result.audio_properties.sample_rate == 8000
    assert result.audio_properties.channels == 1
    assert Path(result.temp_file_path).read_bytes() == audio
    assert Path(result.temp_file_path).suffix == ".wav"
    assert not result.pii_scan.pii_detected
    assert result.pii_scan.affected_fields == []


def test_repeated_intake_uses_distinct_ids_and_files():
    audio = AudioInput(audio_data=_make_wav_bytes(0.01), filename="call.wav")
    first, second = run_intake(audio), run_intake(audio)
    assert first.call_id != second.call_id
    assert first.temp_file_path != second.temp_file_path


@pytest.mark.parametrize("payload", [b"", b"not audio", b"%PDF-1.7"])
def test_invalid_input_leaves_no_file(payload, tmp_path):
    result = run_intake(AudioInput(audio_data=payload, filename="pretend.wav"))
    assert not result.validation_passed
    assert result.validation_error
    assert result.temp_file_path is None
    assert list(tmp_path.iterdir()) == []


def test_size_limit_rejects_valid_audio_without_writing(monkeypatch, tmp_path):
    audio = _make_wav_bytes(0.1)
    monkeypatch.setattr(audio_utils, "MAX_FILE_SIZE_BYTES", len(audio) - 1)
    result = run_intake(AudioInput(audio_data=audio, filename="large.wav"))
    assert not result.validation_passed
    assert "filesize" in result.validation_error
    assert list(tmp_path.iterdir()) == []


def test_exact_size_and_duration_limits_are_accepted(monkeypatch):
    audio = _make_wav_bytes(1)
    monkeypatch.setattr(audio_utils, "MAX_FILE_SIZE_BYTES", len(audio))
    monkeypatch.setattr("src.agents.intake.MAX_DURATION_SECONDS", 1)
    assert run_intake(AudioInput(audio_data=audio, filename="boundary.wav")).validation_passed


@pytest.mark.parametrize(
    "value",
    [
        "123-45-6789",
        "4111 1111 1111 1111",
        "person@example.com",
        "212-555-0123",
    ],
)
@pytest.mark.parametrize("field", ["caller_id", "department"])
def test_metadata_pii_is_flagged_by_field(value, field):
    audio = AudioInput(audio_data=_make_wav_bytes(0.01), filename="call.wav", **{field: value})
    result = run_intake(audio)
    assert result.validation_passed
    assert result.pii_scan.pii_detected
    assert result.pii_scan.affected_fields == [field]
    assert value not in result.pii_scan.model_dump_json()


def test_clean_metadata_is_not_flagged():
    result = run_intake(
        AudioInput(
            audio_data=_make_wav_bytes(0.01),
            filename="call.wav",
            caller_id="anonymous",
            department="support",
        )
    )
    assert not result.pii_scan.pii_detected
    assert result.pii_scan.affected_fields == []


@pytest.mark.parametrize(
    "payload", [b"ID3broken", b"fLaCbroken", b"\x00\x00\x00\x18ftypM4A broken"]
)
def test_malformed_compressed_audio_fails_without_file(payload, tmp_path):
    result = run_intake(AudioInput(audio_data=payload, filename="broken.audio"))
    assert not result.validation_passed
    assert result.validation_error
    assert result.temp_file_path is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "container,codec,suffix",
    [
        ("mp3", "libmp3lame", ".mp3"),
        ("mp4", "aac", ".m4a"),
        ("flac", "flac", ".flac"),
    ],
)
def test_real_compressed_audio_intake_ignores_filename(container, codec, suffix, monkeypatch):
    # PyAV ships with faster-whisper; no external ffmpeg executable or sample download.
    import av
    import numpy as np

    stream = BytesIO()
    with av.open(stream, "w", format=container) as output:
        encoder = output.add_stream(codec, rate=16000)
        encoder.layout = "mono"
        frame = av.AudioFrame.from_ndarray(
            np.zeros((1, 16000), dtype=np.int16), format="s16", layout="mono"
        )
        frame.sample_rate = 16000
        for packet in encoder.encode(frame):
            output.mux(packet)
        for packet in encoder.encode(None):
            output.mux(packet)
    payload = stream.getvalue()
    audio = AudioInput(audio_data=payload, filename="wrong.wav")
    result = run_intake(audio)
    assert result.validation_passed, result.validation_error
    assert result.audio_properties.duration_seconds == pytest.approx(1, abs=0.15)
    assert result.audio_properties.sample_rate == 16000
    assert result.audio_properties.channels == 1
    assert Path(result.temp_file_path).suffix == suffix
    assert Path(result.temp_file_path).read_bytes() == payload

    monkeypatch.setattr("src.agents.intake.MAX_DURATION_SECONDS", 0.5)
    rejected = run_intake(audio)
    assert not rejected.validation_passed
    assert "duration" in rejected.validation_error.lower()
    assert rejected.temp_file_path is None


def test_multiple_metadata_fields_are_reported_once():
    result = run_intake(
        AudioInput(
            audio_data=_make_wav_bytes(0.01),
            filename="call.wav",
            caller_id="123-45-6789 / person@example.com",
            department="212-555-0123",
        )
    )
    assert result.pii_scan.affected_fields == ["caller_id", "department"]


def test_failed_results_do_not_share_mutable_pii_state():
    first = run_intake(AudioInput(audio_data=b"", filename="empty.wav"))
    first.pii_scan.affected_fields.append("caller_id")
    second = run_intake(AudioInput(audio_data=b"", filename="empty.wav"))
    assert second.pii_scan.affected_fields == []
