"""Local, offline Whisper smoke using the first 12 seconds of an existing sample."""

import json
import os
import tempfile
import time
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["DIARIZATION_BACKEND"] = "heuristic"
os.environ["WHISPER_MODEL_SIZE"] = "tiny"
os.environ.pop("DIARIZATION_DEBUG", None)

import av
import numpy as np
from scipy.io import wavfile

from src.agents import transcription as t
from src.agents.intake import run_intake
from src.database.connection import _reset_engine_state
from src.graph.state import AudioInput

samples = sorted(Path("data/samples/samples").glob("*.mp3"))
assert samples, "No existing sample MP3"
with tempfile.TemporaryDirectory(prefix="m3-smoke-") as temp:
    os.environ["DB_PATH"] = str(Path(temp) / "cache.sqlite3")
    _reset_engine_state()
    chunks = []
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    count = 0
    with av.open(str(samples[0])) as source:
        for frame in source.decode(audio=0):
            for decoded in resampler.resample(frame):
                chunk = decoded.to_ndarray().flatten()
                chunks.append(chunk)
                count += len(chunk)
            if count >= 12 * 16000:
                break
    output = Path(temp) / "sample.wav"
    wavfile.write(output, 16000, np.concatenate(chunks)[: 12 * 16000])
    audio = output.read_bytes()
    first_intake = run_intake(AudioInput(audio_data=audio, filename="sample.wav"))
    second_intake = run_intake(AudioInput(audio_data=audio, filename="sample.wav"))
    try:
        started = time.perf_counter()
        first = t.run_transcription(first_intake)
        fresh_sec = time.perf_counter() - started
        assert first.segments and first.full_text
        assert t.get_last_transcription_diagnostics().get("cache_hit") is not True

        def no_second_inference():
            raise AssertionError("Cache hit must not load Whisper")

        t._get_whisper_model = no_second_inference
        started = time.perf_counter()
        second = t.run_transcription(second_intake)
        cached_sec = time.perf_counter() - started
        assert t.get_last_transcription_diagnostics()["cache_hit"]
        assert second.call_id == second_intake.call_id != first.call_id
        assert second.segments == first.segments
        print(
            json.dumps(
                {
                    "sample": samples[0].name,
                    "duration_sec": 12,
                    "model": "tiny",
                    "backend": "heuristic",
                    "segments": len(first.segments),
                    "fresh_sec": round(fresh_sec, 3),
                    "cached_sec": round(cached_sec, 3),
                    "cached_payload_equal": True,
                    "call_id_replaced": True,
                }
            )
        )
    finally:
        for intake in (first_intake, second_intake):
            if intake.temp_file_path:
                Path(intake.temp_file_path).unlink(missing_ok=True)
        _reset_engine_state()
