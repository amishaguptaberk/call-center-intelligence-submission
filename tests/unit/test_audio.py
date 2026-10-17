import wave
from io import BytesIO
from types import SimpleNamespace

import pytest

from src.utils import audio


def make_wav(seconds=5, rate=16000, channels=1):
    stream = BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\0\0" * int(seconds * rate) * channels)
    return stream.getvalue()


@pytest.mark.parametrize(
    "header,expected",
    [
        (b"RIFF\0\0\0\0WAVE", "wav"),
        (b"ID3", "mp3"),
        (b"\xff\xfb\x90\0", "mp3"),
        (b"fLaC", "flac"),
        (b"\0\0\0\x20ftypM4A ", "m4a"),
        (b"OggS", None),
        (b"RIFF\0\0\0\0AVI ", None),
        (b"\0" * 12 + b"ID3", None),
        (b"\xff", None),
        (b"", None),
    ],
)
def test_detection(header, expected):
    assert audio.detect_audio_format(header) == expected


def test_validation_boundaries_and_filename_independence():
    assert audio.MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024
    assert audio.MAX_DURATION_SECONDS == 3600
    assert set(audio.SUPPORTED_FORMATS) == {"wav", "mp3", "flac", "m4a"}
    assert not audio.validate_audio_file(b"", "empty.wav").is_valid
    assert not audio.validate_audio_file(b"OggS", "pretend.wav").is_valid
    data = b"ID3" + b"\0" * (audio.MAX_FILE_SIZE_BYTES - 3)
    assert audio.validate_audio_file(data, "wrong.ogg") == audio.ValidationResult(True)
    assert "exceeds maximum" in audio.validate_audio_file(data + b"\0", "big.wav").error


def test_wav_properties():
    assert audio.extract_audio_properties(make_wav(channels=2), "wav") == {
        "duration_seconds": 5.0,
        "sample_rate": 16000,
        "channels": 2,
    }


@pytest.mark.parametrize("format", ["wav", "mp3", "flac", "m4a", "ogg"])
def test_corrupt_or_unsupported_properties_raise_typed_error(format):
    with pytest.raises(audio.AudioValidationError):
        audio.extract_audio_properties(b"not audio", format)


@pytest.mark.parametrize("format,parser", [("mp3", "MP3"), ("flac", "FLAC"), ("m4a", "MP4")])
def test_mutagen_property_contract(monkeypatch, format, parser):
    def read(stream):
        assert stream.read() == b"encoded audio"
        return SimpleNamespace(info=SimpleNamespace(length=2.5, sample_rate=44100, channels=2))

    monkeypatch.setattr(audio, parser, read)
    assert audio.extract_audio_properties(b"encoded audio", format) == {
        "duration_seconds": 2.5,
        "sample_rate": 44100,
        "channels": 2,
    }


@pytest.mark.parametrize(
    "changes",
    [{"length": float("nan")}, {"length": -1}, {"sample_rate": 0}, {"channels": 0}],
)
def test_invalid_properties_raise_typed_error(monkeypatch, changes):
    info = {"length": 2.0, "sample_rate": 16000, "channels": 1} | changes
    monkeypatch.setattr(audio, "MP3", lambda _: SimpleNamespace(info=SimpleNamespace(**info)))
    with pytest.raises(audio.AudioValidationError):
        audio.extract_audio_properties(b"audio", "mp3")
