"""Manually run Milestone 3 transcription on one sample recording.

Writes the full report to diagnostics/debug.log (and prints to the terminal).

Usage:
  DIARIZATION_BACKEND=acoustic .venv/bin/python try_transcription.py
  DIARIZATION_BACKEND=acoustic .venv/bin/python try_transcription.py data/samples/samples/sample_02.mp3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.agents.call_bounds import call_bounds_notice, call_bounds_summary
from src.agents.intake import run_intake
from src.agents.transcription import (
    get_last_transcription_diagnostics,
    run_transcription,
)
from src.agents.wait_events import (
    compute_wait_events,
    for_display,
    wait_summary_line,
)
from src.graph.state import AudioInput

_DEFAULT_SAMPLE = Path("data/samples/samples/sample_01.mp3")
_DEFAULT_LOG = Path("diagnostics/debug.log")


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


def _fmt_ts(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Milestone 3 transcription; tee output to diagnostics/debug.log."
    )
    parser.add_argument(
        "audio",
        nargs="?",
        default=str(_DEFAULT_SAMPLE),
        help=f"Path to .mp3/.wav (default: {_DEFAULT_SAMPLE})",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=_DEFAULT_LOG,
        help=f"Log file path (default: {_DEFAULT_LOG})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to also write transcript + diagnostics JSON",
    )
    args = parser.parse_args()

    audio_file = Path(args.audio)
    if not audio_file.is_file():
        print(f"Audio not found: {audio_file.resolve()}")
        return 1

    args.log.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(args.log, "w", encoding="utf-8")
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(original_stdout, log_file)
    sys.stderr = _Tee(original_stderr, log_file)

    try:
        print(f"Writing diagnostics to {args.log.resolve()}")
        print(f"Audio: {audio_file}")

        audio_input = AudioInput(
            audio_data=audio_file.read_bytes(),
            filename=audio_file.name,
        )
        intake_result = run_intake(audio_input)
        if not intake_result.validation_passed:
            print(f"intake failed: {intake_result.validation_error}")
            return 1

        result = run_transcription(intake_result)
        diagnostics = get_last_transcription_diagnostics() or {}

        print("\n" + "=" * 90)
        print("TRANSCRIPTION DIAGNOSTIC REPORT")
        print(f"Audio: {audio_file}")
        print(f"Call ID: {result.call_id}")
        print(f"Language: {result.language}")
        print(f"Total segments: {len(result.segments)}")
        print("=" * 90)

        display_segments, bounds = for_display(result.segments)
        waits = compute_wait_events(display_segments)
        print(f"\n{call_bounds_summary(bounds)}")
        print(call_bounds_notice(bounds))
        print(wait_summary_line(waits))

        for i, segment in enumerate(display_segments, start=1):
            print(
                f"\n#{i:02d} [{_fmt_ts(segment.start_time)} - {_fmt_ts(segment.end_time)}] "
                f"({segment.start_time:.2f}s – {segment.end_time:.2f}s) "
                f"{segment.speaker:<10} "
                f"confidence={segment.confidence:.2f}"
            )
            print(f"    {segment.text.strip()}")

        print("\n" + "=" * 90)
        print("FULL TRANSCRIPT (in-call only, hold markers)")
        print("=" * 90)
        print(call_bounds_summary(bounds))
        print(call_bounds_notice(bounds))
        print(wait_summary_line(waits))
        for segment in display_segments:
            print(
                f"[{_fmt_ts(segment.start_time)}-{_fmt_ts(segment.end_time)}] "
                f"{segment.speaker}: {segment.text.strip()}"
            )

        role_mapping = diagnostics.get("role_mapping") or {}
        absorbed = diagnostics.get("absorbed_ambiguous_words") or []
        bleed = diagnostics.get("boundary_bleed_candidates") or []
        amb_utts = diagnostics.get(
            "ambiguous_or_unmapped_utterances",
            diagnostics.get("unresolved_ambiguous_utterances"),
        )

        print("\n" + "-" * 90)
        print("PIPELINE DIAGNOSTICS (compact)")
        print("-" * 90)
        print(f"  backend:            {diagnostics.get('backend')}")
        print(f"  label_source:       {diagnostics.get('label_source')}")
        print(f"  cache_hit:          {diagnostics.get('cache_hit', False)}")
        print(f"  ok:                 {diagnostics.get('ok')}")
        if diagnostics.get("fallback_activated"):
            print(f"  fallback:           {diagnostics.get('fallback_reason')}")
        if diagnostics.get("note"):
            print(f"  note:               {diagnostics.get('note')}")

        label_source = str(diagnostics.get("label_source") or "")
        is_acoustic = label_source in {"acoustic", "cached"} or (
            diagnostics.get("backend") in {"acoustic", "hybrid"}
            and label_source not in {"heuristic", "heuristic_fallback"}
        )
        if is_acoustic and label_source != "heuristic":
            print(f"  model:              {diagnostics.get('model')}")
            print(f"  turn_first:         {diagnostics.get('turn_first_grouping')}")
            print(
                f"  role_mapping:       {role_mapping.get('method')} → {role_mapping.get('mapping')}"
            )
            if role_mapping.get("notes"):
                print(f"  role_notes:         {role_mapping.get('notes')}")
            print(f"  ambiguous_words:    {diagnostics.get('ambiguous_words')}")
            print(f"  ambiguous_utts:     {amb_utts}")
            print(
                f"  absorbed_words:     {diagnostics.get('absorbed_ambiguous_count', len(absorbed))}"
            )
            if absorbed:
                for item in absorbed:
                    print(
                        f"    - {item.get('word')!r} [{item.get('start')}–{item.get('end')}] "
                        f"{item.get('original_reason')} → {item.get('absorbed_into_speaker_id')}"
                    )
            print(
                f"  boundary_candidates:{diagnostics.get('boundary_bleed_candidate_count', len(bleed))}"
            )
            if bleed:
                for item in bleed:
                    print(
                        f"    - {item.get('word')!r} [{item.get('start')}–{item.get('end')}] "
                        f"majority={item.get('majority_overlap_speaker')} "
                        f"hyp_clamp={item.get('hypothetical_clamp_speaker')}"
                    )
        print(f"  segment_count:      {diagnostics.get('segment_count', len(result.segments))}")
        timing = diagnostics.get("timing_sec") or {}
        if timing:
            print("\n" + "-" * 90)
            print("TIMING (seconds)")
            print("-" * 90)
            for key in (
                "whisper_model_init",
                "whisper_transcribe",
                "community1_device",
                "community1_pipeline_init",
                "community1_inference",
                "community1_audio_load",
                "community1_pipeline_forward",
                "align_group_role",
                "heuristic_diarize",
                "total_run_transcription",
            ):
                if key in timing and timing[key] is not None:
                    val = timing[key]
                    if isinstance(val, (int, float)):
                        print(f"  {key + ':':<28} {val:.3f}")
                    else:
                        print(f"  {key + ':':<28} {val}")

        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "audio": str(audio_file),
                "call_id": result.call_id,
                "language": result.language,
                "full_text": result.full_text,
                "segments": [
                    {
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "speaker": s.speaker,
                        "confidence": s.confidence,
                        "text": s.text,
                    }
                    for s in result.segments
                ],
                "diagnostics": diagnostics,
            }
            args.out.write_text(json.dumps(payload, indent=2) + "\n")
            print(f"\nWrote JSON {args.out}")

        print(f"\nSTATUS: SUCCESS — wrote {args.log}")
        return 0
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
