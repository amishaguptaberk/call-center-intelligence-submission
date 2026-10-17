import re
import tempfile
import uuid
import wave
from io import BytesIO

from src.graph.state import AudioInput, AudioProperties, IntakeResult, PIIScanResult
from src.utils.audio import (
    MAX_DURATION_SECONDS,
    AudioValidationError,
    detect_audio_format,
    extract_audio_properties,
    validate_audio_file,
)

_EMPTY_AUDIO_PROPS = AudioProperties(duration_seconds=0.0, sample_rate=0, channels=0)
_EMPTY_PII = PIIScanResult()


def _make_failed_result(call_id: str, error: str) -> IntakeResult:
    return IntakeResult(
        call_id=call_id,
        validation_passed=False,
        validation_error=error,
        audio_properties=_EMPTY_AUDIO_PROPS.model_copy(deep=True),
        pii_scan=_EMPTY_PII.model_copy(deep=True),
        temp_file_path=None,
    )


def run_intake(audio_input: AudioInput) -> IntakeResult:
    """Validate incoming audio and return a structured intake result."""
    call_id = str(uuid.uuid4())
    audio_format = detect_audio_format(audio_bytes=audio_input.audio_data)
    if audio_format == "wav":
        try:
            with wave.open(BytesIO(audio_input.audio_data), "rb") as wav_reader:
                frames_count = wav_reader.getnframes()
                sample_rate = wav_reader.getframerate()
            if sample_rate <= 0:
                return _make_failed_result(call_id, "Invalid WAV sample rate")
            duration = frames_count / sample_rate
            if duration > MAX_DURATION_SECONDS:
                return _make_failed_result(
                    call_id=call_id,
                    error="audio duration exceeds maximum allowed duration",
                )
        except (wave.Error, EOFError, OSError):
            return _make_failed_result(call_id, "Unable to read WAV audio")

    result = validate_audio_file(audio_bytes=audio_input.audio_data, filename=audio_input.filename)

    if not result.is_valid:
        return _make_failed_result(call_id=call_id, error=result.error or "audio validation failed")

    if audio_format != "wav":
        try:
            audio_properties = extract_audio_properties(
                audio_bytes=audio_input.audio_data, audio_format=audio_format
            )
        except AudioValidationError as e:
            return _make_failed_result(call_id=call_id, error=str(e))
        if audio_properties["duration_seconds"] > MAX_DURATION_SECONDS:
            return _make_failed_result(
                call_id,
                "Audio duration exceeds maximum allowed duration",
            )
    else:
        try:
            audio_properties = extract_audio_properties(
                audio_bytes=audio_input.audio_data, audio_format="wav"
            )
        except AudioValidationError as e:
            return _make_failed_result(call_id=call_id, error=str(e))
    properties_model = AudioProperties(**audio_properties)

    with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_file:
        temp_file.write(audio_input.audio_data)
        temp_file_path = temp_file.name

    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_PATTERN = re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

    patterns = [SSN_PATTERN, CREDIT_PATTERN, EMAIL_PATTERN, PHONE_PATTERN]

    metadata = {
        "caller_id": audio_input.caller_id,
        "department": audio_input.department,
    }

    affected_fields = []

    for field_name, value in metadata.items():
        if value is None:
            continue
        if any(pattern.search(value) for pattern in patterns):
            affected_fields.append(field_name)

    pii_detected = bool(affected_fields)
    pii_scan = PIIScanResult(pii_detected=pii_detected, affected_fields=affected_fields)

    return IntakeResult(
        call_id=call_id,
        validation_passed=True,
        audio_properties=properties_model,
        pii_scan=pii_scan,
        temp_file_path=temp_file_path,
    )
