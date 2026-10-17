"""A/B: acoustic clusters only vs acoustic + role-mapping heuristics on sample_01.

Arms (same Community-1 + align + group; no QUESTION_SWITCH / SILENCE_GAP / FALLBACK):
  acoustic_only — SPEAKER_id clusters; Agent/Customer via best global permutation
                  against annotation (eval matching only; no text/role heuristics).
  acoustic_plus_role_heuristics — production map_roles (opening cues / fallbacks).

Usage:
  .venv/bin/python scripts/experiments/compare_role_mapping_sample01.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.eval_sample01_diarization import score_against_annotation  # noqa: E402
from src.agents.acoustic import (  # noqa: E402
    RoleMapping,
    WordTiming,
    align_words_to_speakers,
    group_utterances,
    label_utterances,
    map_roles,
    run_community1,
)
from src.agents.intake import run_intake  # noqa: E402
from src.agents.transcription import _clean_transcript_text, _get_whisper_model  # noqa: E402
from src.graph.state import AudioInput, TranscriptionSegment  # noqa: E402


def _utterances_to_segments(labeled) -> list[TranscriptionSegment]:
    out: list[TranscriptionSegment] = []
    for utt, role in labeled:
        if not utt.text.strip():
            continue
        if role is None or utt.ambiguous:
            speaker = "Ambiguous"
            conf = min(utt.confidence, 0.3)
        else:
            speaker = role
            conf = utt.confidence
        out.append(
            TranscriptionSegment(
                start_time=utt.start,
                end_time=utt.end,
                text=utt.text,
                speaker=speaker,
                confidence=conf,
            )
        )
    return out


def _best_permutation_mapping(speaker_ids: list[str], utterances, annotation: dict) -> RoleMapping:
    """Eval-only: pick SPEAKER→role bijection that maximizes clear-interval accuracy."""
    roles = ("Agent", "Customer")
    if len(speaker_ids) == 0:
        return RoleMapping({}, "empty", "No speakers.")
    if len(speaker_ids) == 1:
        mapping = {speaker_ids[0]: "Agent"}
        return RoleMapping(mapping, "single_speaker_eval", "Only one cluster.")

    # For >2 speakers, try all injections into Agent/Customer is under-specified;
    # sample_01 is 2-speaker. Map first two via permutations; extras → Ambiguous.
    primary = sorted(speaker_ids)[:2]
    best: RoleMapping | None = None
    best_acc = -1.0
    for perm in itertools.permutations(roles, len(primary)):
        clean = {sid: role for sid, role in zip(primary, perm)}
        labeled = label_utterances(utterances, RoleMapping(clean, "perm", ""))
        segs = _utterances_to_segments(labeled)
        score = score_against_annotation(segs, annotation)
        acc = score["accuracy"] or 0.0
        if acc > best_acc:
            best_acc = acc
            best = RoleMapping(
                clean,
                "best_permutation_vs_annotation",
                f"Eval-only matching; accuracy={acc:.4f}; mapping={clean}",
            )
    assert best is not None
    return best


def _error_ids(details: list[dict]) -> set[str]:
    return {d["id"] for d in details if not d["correct"]}


def main() -> int:
    os.environ.setdefault("DIARIZATION_BACKEND", "acoustic")
    audio_path = ROOT / "data/samples/samples/sample_01.mp3"
    ann_path = ROOT / "evaluation/annotations/recordings/sample_01/annotation.v2.json"
    annotation = json.loads(ann_path.read_text())

    intake = run_intake(AudioInput(audio_data=audio_path.read_bytes(), filename=audio_path.name))
    if not intake.validation_passed:
        print("intake failed", intake.validation_error)
        return 1

    t0 = time.perf_counter()
    model = _get_whisper_model()
    whisper_segments, _info = model.transcribe(
        audio=str(intake.temp_file_path),
        beam_size=1,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    whisper_segments = list(whisper_segments)

    words: list[WordTiming] = []
    asr_spans: list[tuple[float, float]] = []
    for seg in whisper_segments:
        asr_spans.append((float(seg.start), float(seg.end)))
        if seg.words:
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                token = _clean_transcript_text(w.word)
                if not token:
                    continue
                words.append(WordTiming(token, float(w.start), float(w.end)))
        else:
            text = _clean_transcript_text(seg.text)
            if text:
                words.append(WordTiming(text, float(seg.start), float(seg.end)))

    # One Community-1 pass shared by both arms (same file Whisper used).
    intervals, _c1_timing = run_community1(Path(intake.temp_file_path))
    attributed = align_words_to_speakers(words, intervals)
    utterances, _absorptions = group_utterances(
        attributed, intervals=intervals, asr_spans=asr_spans, turn_first=True
    )
    runtime = time.perf_counter() - t0

    speaker_ids = sorted({u.speaker_id for u in utterances if u.speaker_id is not None})

    heuristic_roles = map_roles(utterances)
    acoustic_only_roles = _best_permutation_mapping(speaker_ids, utterances, annotation)

    arms = {
        "acoustic_only": acoustic_only_roles,
        "acoustic_plus_role_heuristics": heuristic_roles,
    }
    arm_scores: dict[str, dict] = {}
    for name, roles in arms.items():
        labeled = label_utterances(utterances, roles)
        segs = _utterances_to_segments(labeled)
        score = score_against_annotation(segs, annotation)
        arm_scores[name] = {
            "role_mapping": {
                "method": roles.method,
                "mapping": roles.mapping,
                "notes": roles.notes,
            },
            "score": {
                "clear_intervals": score["clear_intervals"],
                "correct": score["correct"],
                "incorrect": score["incorrect"],
                "accuracy": score["accuracy"],
                "confusions": score["confusions"],
            },
            "details": score["details"],
            "errors": [d for d in score["details"] if not d["correct"]],
        }

    only_errs = _error_ids(arm_scores["acoustic_only"]["details"])
    heur_errs = _error_ids(arm_scores["acoustic_plus_role_heuristics"]["details"])

    detail_by_id = {d["id"]: d for d in arm_scores["acoustic_only"]["details"]}
    heur_by_id = {d["id"]: d for d in arm_scores["acoustic_plus_role_heuristics"]["details"]}

    fixed_by_heuristics = sorted(only_errs - heur_errs)
    newly_introduced_by_heuristics = sorted(heur_errs - only_errs)
    still_wrong_both = sorted(only_errs & heur_errs)

    def _row(iid: str) -> dict:
        a = detail_by_id[iid]
        b = heur_by_id[iid]
        return {
            "id": iid,
            "gt": a["gt"],
            "acoustic_only_pred": a["pred"],
            "role_heuristics_pred": b["pred"],
            "start_sec": next(iv["start_sec"] for iv in annotation["intervals"] if iv["id"] == iid),
            "end_sec": next(iv["end_sec"] for iv in annotation["intervals"] if iv["id"] == iid),
        }

    report = {
        "recording_id": "sample_01",
        "annotation": str(ann_path.relative_to(ROOT)),
        "runtime_sec": round(runtime, 3),
        "design": {
            "shared": "Community-1 + word align + utterance group",
            "acoustic_only": (
                "Agent/Customer via best global SPEAKER permutation vs annotation "
                "(eval matching only; no opening-cue / first-speaker role heuristics)"
            ),
            "acoustic_plus_role_heuristics": "production map_roles()",
            "excluded": [
                "QUESTION_SWITCH",
                "SILENCE_GAP",
                "FALLBACK speaker-switch rules",
            ],
        },
        "arms": {
            name: {
                "role_mapping": arm_scores[name]["role_mapping"],
                "score": arm_scores[name]["score"],
                "errors": arm_scores[name]["errors"],
            }
            for name in arms
        },
        "delta": {
            "fixed_by_role_heuristics": [_row(i) for i in fixed_by_heuristics],
            "newly_introduced_by_role_heuristics": [
                _row(i) for i in newly_introduced_by_heuristics
            ],
            "still_wrong_under_both": [_row(i) for i in still_wrong_both],
            "summary": {
                "acoustic_only_errors": len(only_errs),
                "role_heuristics_errors": len(heur_errs),
                "fixed": len(fixed_by_heuristics),
                "newly_introduced": len(newly_introduced_by_heuristics),
                "unchanged_errors": len(still_wrong_both),
                "same_mapping_as_oracle": (acoustic_only_roles.mapping == heuristic_roles.mapping),
            },
        },
    }

    out_path = ROOT / "evaluation/reports/sample01_role_mapping_ab.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n")

    # Console summary (no transcript text)
    print(
        json.dumps(
            {
                "runtime_sec": report["runtime_sec"],
                "arms": {
                    k: {
                        "mapping": v["role_mapping"],
                        "score": v["score"],
                        "error_ids": [e["id"] for e in v["errors"]],
                    }
                    for k, v in report["arms"].items()
                },
                "delta": report["delta"],
            },
            indent=2,
        )
    )
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
