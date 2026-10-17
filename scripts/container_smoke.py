"""Synthetic fixture verification; never invokes live ASR or a model provider."""

import argparse
import base64
import json
import os
import re
import sqlite3
import tempfile
import uuid
import wave
import zlib
from pathlib import Path

from src.database.connection import init_db
from src.graph.state import (
    QADimensionScore,
    QAScoreResult,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)
from src.services.history import history_report
from src.services.pipeline import process_call

MARKER = "SYNTHETIC FIXTURE ONLY"
RAW = f"{MARKER}: Call 555-123-4567 or fixture@example.com. Issue resolved."
SAFE = f"{MARKER}: Call [REDACTED_PHONE] or [REDACTED_EMAIL]. Issue resolved."
PREFIX = "synthetic-container-fixture-"


def assert_safe(transcript):
    assert transcript.full_text == SAFE
    assert [segment.text for segment in transcript.segments] == [SAFE]


def transcribe(intake):
    assert intake.validation_passed
    assert intake.audio_properties.duration_seconds == 1.0
    return TranscriptionResult(
        call_id=intake.call_id,
        full_text=RAW,
        language="en",
        segments=[
            TranscriptionSegment(
                start_time=0, end_time=1, text=RAW, speaker="Synthetic customer", confidence=1
            )
        ],
    )


def summarize(transcript):
    assert_safe(transcript)
    return SummaryResult(
        call_id=transcript.call_id,
        call_purpose=MARKER,
        key_discussion_points=[MARKER, "Synthetic issue", "Synthetic resolution"],
        resolution_status="resolved",
        sentiment_trajectory="Synthetic neutral",
    )


def score_qa(transcript, summary):
    from src.agents.qa_scoring import DIMENSION_WEIGHTS

    assert_safe(transcript)
    assert summary.call_id == transcript.call_id
    scores = [
        QADimensionScore(dimension=name, score=3, justification=MARKER)
        for name in DIMENSION_WEIGHTS
    ]
    weighted = round(sum(DIMENSION_WEIGHTS[item.dimension] * item.score for item in scores), 2)
    assert weighted == 3.0
    return QAScoreResult(
        call_id=transcript.call_id, dimension_scores=scores, overall_score=weighted
    )


def verify_exports(result, call_id):
    assert result.ok, result.status_md
    payload = Path(result.json_path).read_text()
    report = json.loads(payload)
    assert report["call_id"] == call_id
    for key in ("intake", "transcription", "summary", "qa_scores"):
        assert report[key]["call_id"] == call_id
    assert report["transcription"]["full_text"] == SAFE
    assert report["transcription"]["segments"][0]["text"] == SAFE
    assert report["summary"]["call_purpose"] == MARKER
    assert report["qa_scores"]["overall_score"] == 3.0
    assert SAFE in result.transcript
    pdf = Path(result.pdf_path).read_bytes()
    assert pdf.startswith(b"%PDF-")
    # ReportLab's default content streams use ASCII85 followed by Flate compression.
    streams = re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.DOTALL)
    assert streams
    text = b"\n".join(
        zlib.decompress(base64.a85decode(stream.strip(), adobe=True)) for stream in streams
    ).decode("latin1")
    assert call_id in text and MARKER in text and "3.00/5" in text
    assert "REDACTED_PHONE" in text and "REDACTED_EMAIL" in text
    for raw in ("555-123-4567", "fixture@example.com"):
        assert raw not in payload and raw not in text and raw not in result.transcript
    for path in (result.pdf_path, result.json_path):
        Path(path).unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-persistence", action="store_true")
    args = parser.parse_args()
    # Require an explicit isolated database; never fall back to a developer database.
    database = Path(os.environ["DB_PATH"])
    init_db()
    if args.check_persistence:
        with sqlite3.connect(database) as db:
            rows = db.execute(
                "SELECT call_id, report_json FROM call_records WHERE audio_filename LIKE ?",
                (PREFIX + "%.wav",),
            ).fetchall()
        assert len(rows) == 1, "Expected exactly one persisted synthetic fixture"
        call_id, stored = rows[0]
        assert json.loads(stored)["summary"]["call_purpose"] == MARKER
        verify_exports(history_report(call_id), call_id)
    else:
        from src.graph import nodes

        with sqlite3.connect(database) as db:
            assert db.execute("SELECT count(*) FROM call_records").fetchone()[0] == 0
        originals = nodes.run_transcription, nodes.summarize, nodes.score_qa
        nodes.run_transcription, nodes.summarize, nodes.score_qa = transcribe, summarize, score_qa
        try:
            with tempfile.TemporaryDirectory(prefix=PREFIX) as directory:
                recording = Path(directory) / f"{PREFIX}{uuid.uuid4().hex}.wav"
                with wave.open(str(recording), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(16000)
                    audio.writeframes(b"\0\0" * 16000)
                result = process_call(recording, department=MARKER)
                assert result.ok, result.status_md
                report = json.loads(Path(result.json_path).read_text())
                call_id = report["call_id"]
                assert not Path(report["intake"]["temp_file_path"]).exists()
                verify_exports(result, call_id)
        finally:
            nodes.run_transcription, nodes.summarize, nodes.score_qa = originals
    print(
        json.dumps(
            {
                "synthetic_fixture": True,
                "call_id": call_id,
                "overall_score": 3.0,
                "persistence_verified": args.check_persistence,
            }
        )
    )


if __name__ == "__main__":
    main()
