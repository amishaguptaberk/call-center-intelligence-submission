import math
import wave
from dataclasses import dataclass
from io import BytesIO

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

MAX_FILE_SIZE_BYTES = 52428800
MAX_DURATION_SECONDS = 3600
SUPPORTED_FORMATS = ("wav", "flac", "mp3", "m4a")


class AudioValidationError(Exception):
    pass


@dataclass
class ValidationResult:
    is_valid: bool
    error: str | None = None


def detect_audio_format(audio_bytes: bytes) -> str | None:
    header = audio_bytes[:12]
    if header[0:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "wav"
    elif header[0:4] == b"fLaC":
        return "flac"
    elif (
        header.startswith(b"ID3")
        or len(header) >= 2
        and header[0] == 0xFF
        and (header[1] & 0xE0 == 0xE0)
    ):
        return "mp3"
    elif header[4:8] == b"ftyp":
        return "m4a"
    return None


def validate_audio_file(audio_bytes: bytes, filename: str) -> ValidationResult:
    if not audio_bytes:
        return ValidationResult(is_valid=False, error="Empty file")
    if len(audio_bytes) > MAX_FILE_SIZE_BYTES:
        return ValidationResult(is_valid=False, error=f"{filename} exceeds maximum filesize")
    if detect_audio_format(audio_bytes=audio_bytes) not in SUPPORTED_FORMATS:
        return ValidationResult(
            is_valid=False, error="Unsupported audio format. Choose WAV, MP3, FLAC, or M4A."
        )
    return ValidationResult(is_valid=True)


def extract_audio_properties(audio_bytes: bytes, audio_format: str) -> dict[str, float | int]:
    if audio_format not in SUPPORTED_FORMATS:
        raise AudioValidationError(f"Unsupported audio format: {audio_format}")

    if audio_format == "wav":
        try:
            with BytesIO(audio_bytes) as stream, wave.open(stream, "rb") as wav_reader:
                frames_count = wav_reader.getnframes()
                sample_rate = wav_reader.getframerate()
                channels = wav_reader.getnchannels()
                expected_bytes = frames_count * channels * wav_reader.getsampwidth()
                if len(wav_reader.readframes(frames_count)) != expected_bytes:
                    raise AudioValidationError("Incomplete WAV audio data")

            if sample_rate <= 0:
                raise AudioValidationError("Invalid WAV sample rate")

            duration = frames_count / sample_rate

        except (wave.Error, EOFError, OSError) as exc:
            raise AudioValidationError("Unable to read WAV audio") from exc

    else:
        format_classes = {
            "mp3": MP3,
            "flac": FLAC,
            "m4a": MP4,
        }

        audio_class = format_classes[audio_format]

        try:
            with BytesIO(audio_bytes) as stream:
                audio_info = audio_class(stream).info

                duration = audio_info.length
                sample_rate = audio_info.sample_rate
                channels = audio_info.channels

        except (MutagenError, EOFError, OSError) as exc:
            raise AudioValidationError(f"Unable to read {audio_format.upper()} audio") from exc

    if not math.isfinite(duration) or duration < 0:
        raise AudioValidationError("Invalid audio duration")

    if sample_rate <= 0:
        raise AudioValidationError("Invalid audio sample rate")

    if channels <= 0:
        raise AudioValidationError("Invalid audio channel count")

    return {
        "duration_seconds": float(duration),
        "sample_rate": int(sample_rate),
        "channels": int(channels),
    }
