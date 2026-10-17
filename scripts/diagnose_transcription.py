"""Batch transcription diagnostics for speaker-assignment inspection."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.intake import run_intake
from src.agents.transcription import (
    get_last_transcription_diagnostics,
    run_transcription,
)
from src.graph.state import AudioInput


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def discover_audio_files(samples_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.mp3", "*.wav"):
        files.extend(samples_dir.rglob(pattern))
    return sorted(files)


def print_transcription_report(result) -> None:
    print("\n" + "=" * 90)
    print("TRANSCRIPTION DIAGNOSTIC REPORT")
    print(f"Call ID: {result.call_id}")
    print(f"Language: {result.language}")
    print(f"Total segments: {len(result.segments)}")
    print("=" * 90)

    for i, segment in enumerate(result.segments, start=1):
        start = f"{int(segment.start_time // 60):02d}:{int(segment.start_time % 60):02d}"
        end = f"{int(segment.end_time // 60):02d}:{int(segment.end_time % 60):02d}"
        print(
            f"\n#{i:02d} [{start} - {end}] "
            f"{segment.speaker.upper():<8} "
            f"Confidence: {segment.confidence:.2f}"
        )
        print(f"    {segment.text.strip()}")

    print("\n" + "=" * 90)
    print("FULL TRANSCRIPT")
    print("=" * 90)
    print(result.full_text)
    print("=" * 90)


def process_recording(audio_path: Path) -> None:
    audio_input = AudioInput(
        audio_data=audio_path.read_bytes(),
        filename=audio_path.name,
    )
    intake_result = run_intake(audio_input)
    if not intake_result.validation_passed:
        raise RuntimeError(f"intake failed: {intake_result.validation_error or 'unknown error'}")
    result = run_transcription(intake_result)
    print_transcription_report(result)
    diagnostics = get_last_transcription_diagnostics()
    if diagnostics:
        print("\n" + "-" * 90)
        print("PIPELINE DIAGNOSTICS (internal; not part of TranscriptionResult)")
        print("-" * 90)
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")


def main() -> int:
    samples_dir = ROOT / "data" / "samples"
    diagnostics_dir = ROOT / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    log_path = diagnostics_dir / "debug.log"

    audio_files = discover_audio_files(samples_dir)
    if not audio_files:
        print(f"No .mp3/.wav files found under {samples_dir}")
        return 1

    log_file = open(log_path, "w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _Tee(original_stdout, log_file)
    sys.stderr = _Tee(original_stderr, log_file)

    succeeded = 0
    failed = 0

    try:
        print(f"Discovered {len(audio_files)} recording(s) under {samples_dir}")
        print(f"Writing diagnostics to {log_path}")

        for audio_path in audio_files:
            relative = audio_path.relative_to(ROOT)
            print("\n" + "#" * 90)
            print(f"FILE: {relative}")
            print("#" * 90)

            try:
                process_recording(audio_path)
                print(f"STATUS: SUCCESS — {relative}")
                succeeded += 1
            except Exception as exc:
                failed += 1
                print(f"STATUS: FAILED — {relative}")
                print(f"ERROR: {exc}")
                traceback.print_exc()

        print("\n" + "#" * 90)
        print("BATCH SUMMARY")
        print("#" * 90)
        print(f"Total: {len(audio_files)}")
        print(f"Succeeded: {succeeded}")
        print(f"Failed: {failed}")
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
