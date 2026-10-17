"""Compare heuristic baseline vs acoustic pipeline on sample_01 annotation.v2.

Usage:
  DIARIZATION_BACKEND=heuristic .venv/bin/python scripts/eval_sample01_diarization.py
  DIARIZATION_BACKEND=acoustic  .venv/bin/python scripts/eval_sample01_diarization.py

Does not modify annotations. Unannotated regions are not scored.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.intake import run_intake
from src.agents.transcription import (
    _diarization_backend,
    get_last_transcription_diagnostics,
    run_transcription,
)
from src.graph.state import AudioInput


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def score_against_annotation(segments, annotation: dict) -> dict:
    correct = incorrect = unscored = 0
    confusions = Counter()
    details = []
    for iv in annotation["intervals"]:
        if iv["status"] != "clear":
            unscored += 1
            continue
        t0, t1 = iv["start_sec"], iv["end_sec"]
        votes = Counter()
        for seg in segments:
            ov = _overlap(seg.start_time, seg.end_time, t0, t1)
            if ov > 0 and seg.speaker in ("Agent", "Customer"):
                votes[seg.speaker] += ov
        if not votes:
            # Ambiguous-only coverage does not count as correct
            incorrect += 1
            details.append({"id": iv["id"], "gt": iv["label"], "pred": None, "correct": False})
            continue
        pred = votes.most_common(1)[0][0]
        hit = pred == iv["label"]
        correct += int(hit)
        incorrect += int(not hit)
        if not hit:
            confusions[f"{iv['label']}->{pred}"] += 1
        details.append({"id": iv["id"], "gt": iv["label"], "pred": pred, "correct": hit})
    n = correct + incorrect
    return {
        "clear_intervals": n,
        "correct": correct,
        "incorrect": incorrect,
        "unscored_non_clear": unscored,
        "accuracy": (correct / n) if n else None,
        "confusions": dict(confusions),
        "details": details,
    }


def main() -> int:
    backend = _diarization_backend()
    audio_path = ROOT / "data/samples/samples/sample_01.mp3"
    ann_path = ROOT / "evaluation/annotations/recordings/sample_01/annotation.v2.json"
    if not audio_path.is_file():
        print(f"Missing audio: {audio_path}")
        return 1
    annotation = json.loads(ann_path.read_text())

    intake = run_intake(AudioInput(audio_data=audio_path.read_bytes(), filename=audio_path.name))
    if not intake.validation_passed:
        print("intake failed", intake.validation_error)
        return 1

    t0 = time.perf_counter()
    try:
        result = run_transcription(intake)
    except Exception as exc:
        print(f"BACKEND={backend} FAILED: {exc}")
        print("diagnostics:", get_last_transcription_diagnostics())
        return 1
    runtime = time.perf_counter() - t0

    report = score_against_annotation(result.segments, annotation)
    out = {
        "backend": backend,
        "runtime_sec": round(runtime, 3),
        "segment_count": len(result.segments),
        "diagnostics": get_last_transcription_diagnostics(),
        "score": {k: v for k, v in report.items() if k != "details"},
        "historical_non_comparable": {
            "heuristics_listen_disagreements_10_of_35": "see evaluation/historical/",
        },
    }
    out_path = ROOT / "evaluation/reports" / f"sample01_{backend}_score.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Strip PII: do not write transcript text
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
