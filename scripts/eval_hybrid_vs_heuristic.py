"""Evaluate hybrid vs heuristic diarization.

sample_01 is scored against annotation.v2.
All 10 samples get latency/fallback stats and continuum proxies
(sentence units labeled by overlapping output segments).

Also caches hybrid predictions under ``evaluation/runs/hybrid/`` (gitignored) and
exports readable transcripts under ``evaluation/local/transcripts/``.

Does not modify annotations. Does not overwrite heuristic_all10_failure_modes.json.

Usage:
  .venv/bin/python scripts/eval_hybrid_vs_heuristic.py
  .venv/bin/python scripts/eval_hybrid_vs_heuristic.py --export-transcripts-only
  .venv/bin/python scripts/eval_hybrid_vs_heuristic.py --force-rerun
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from scripts.eval_sample01_diarization import _overlap, score_against_annotation
from src.agents.acoustic import (
    acoustic_timeout_sec,
    run_acoustic_diarization,
)
from src.agents.intake import run_intake
from src.agents.transcription import (
    _audio_duration_sec,
    _run_heuristic,
    _run_heuristic_with_diagnostics,
    _segments_from_acoustic_dicts,
    _sentence_units_from_whisper,
    _words_and_spans_from_whisper,
)
from src.graph.state import AudioInput, TranscriptionSegment

SAMPLES = sorted((ROOT / "data/samples/samples").glob("sample_*.mp3"))
ANN01 = ROOT / "evaluation/annotations/recordings/sample_01/annotation.v2.json"
OUT = ROOT / "evaluation/reports/hybrid_vs_heuristic_eval.json"
CACHE_DIR = ROOT / "evaluation/runs/hybrid"
TRANSCRIPT_DIR = ROOT / "evaluation/local/transcripts"


def _cache_path(sid: str) -> Path:
    return CACHE_DIR / f"{sid}.prediction.json"


def _transcript_path(sid: str) -> Path:
    return TRANSCRIPT_DIR / f"{sid}.hybrid.txt"


def _label_sentences_from_segments(units, segments) -> list[str]:
    labels = []
    for u in units:
        votes = Counter()
        for s in segments:
            ov = _overlap(s.start_time, s.end_time, u.start, u.end)
            if ov > 0 and s.speaker in ("Agent", "Customer"):
                votes[s.speaker] += ov
        if votes:
            labels.append(votes.most_common(1)[0][0])
        else:
            labels.append("Ambiguous")
    return labels


def continuum_breaks(units, labels) -> int:
    """Count Customer→…→Agent snaps after a Customer sentence (proxy for reply break)."""
    n = 0
    for i in range(len(units) - 1):
        if labels[i] != "Customer":
            continue
        j = i + 1
        while j < len(units) and labels[j] == "Agent" and units[j].act == "statement":
            if units[j].pattern_label is None:
                n += 1
            j += 1
            if j > i + 4:
                break
    return n


def missed_short_acks(units, labels) -> int:
    n = 0
    for i in range(1, len(units)):
        if labels[i] != "Agent" or labels[i - 1] != "Agent":
            continue
        u = units[i]
        if u.act == "ack" or (
            u.word_count <= 4
            and u.text.lower().strip(".,!? ").startswith(("yeah", "yes", "ok", "oh"))
        ):
            n += 1
    return n


def _rows_from_labeled(labeled: list[dict], role_mapping: dict | None) -> list[dict]:
    """Build export rows from acoustic worker payloads (include acoustic speaker_id)."""
    mapping = {}
    if isinstance(role_mapping, dict):
        mapping = role_mapping.get("mapping") or role_mapping
    rows = []
    for item in labeled:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        spk_id = item.get("speaker_id")
        role = item.get("role")
        ambiguous = bool(item.get("ambiguous")) or role is None
        role_label = "Ambiguous" if ambiguous else str(role)
        rows.append(
            {
                "start": float(item["start"]),
                "end": float(item["end"]),
                "text": text,
                "role": role_label,
                "acoustic_speaker_id": spk_id,
                "mapped_role_from_id": mapping.get(spk_id) if spk_id else None,
                "confidence": float(
                    item["confidence"] if item.get("confidence") is not None else 0.0
                ),
            }
        )
    return rows


def _rows_from_segments(segments: list[TranscriptionSegment]) -> list[dict]:
    """Fallback rows when only TranscriptionSegments exist (no acoustic IDs)."""
    return [
        {
            "start": float(s.start_time),
            "end": float(s.end_time),
            "text": s.text,
            "role": s.speaker,
            "acoustic_speaker_id": None,
            "mapped_role_from_id": None,
            "confidence": float(s.confidence),
        }
        for s in segments
        if s.text.strip()
    ]


def write_readable_transcript(sid: str, rows: list[dict], *, meta: dict) -> Path:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = _transcript_path(sid)
    role_map = meta.get("role_mapping") or {}
    lines = [
        f"# Hybrid diarization transcript — {sid}",
        f"# label_source: {meta.get('label_source')}",
        f"# acoustic_verified: {meta.get('acoustic_verified')}",
        f"# fallback_activated: {meta.get('fallback_activated')}",
        f"# role_mapping: {json.dumps(role_map, sort_keys=True) if role_map else '{}'}",
        "# columns: start-end | role | acoustic_id | text",
        "",
    ]
    for r in rows:
        aid = r.get("acoustic_speaker_id") or "—"
        lines.append(
            f"{r['start']:8.2f}-{r['end']:8.2f}  {str(r['role']):10s}  {str(aid):12s}  {r['text']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def save_prediction_cache(sid: str, payload: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(sid)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_prediction_cache(sid: str) -> dict | None:
    path = _cache_path(sid)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def export_transcripts_from_cache() -> int:
    """Write readable transcripts from cached predictions only (no acoustic)."""
    missing = []
    written = []
    for audio in SAMPLES:
        sid = audio.stem
        cache = load_prediction_cache(sid)
        if cache is None:
            missing.append(sid)
            continue
        role_map = cache.get("role_mapping")
        if isinstance(role_map, dict) and "mapping" in role_map:
            role_map = role_map["mapping"]
        path = write_readable_transcript(
            sid,
            cache["rows"],
            meta={
                "label_source": cache.get("label_source"),
                "acoustic_verified": cache.get("acoustic_verified"),
                "fallback_activated": cache.get("fallback_activated"),
                "role_mapping": role_map,
            },
        )
        written.append(str(path))
        print(f"wrote {path}", flush=True)
    if missing:
        print(
            "Missing prediction caches (run full eval once, or --force-rerun):\n  "
            + ", ".join(missing),
            flush=True,
        )
        return 1
    print(f"Exported {len(written)} transcripts under {TRANSCRIPT_DIR}")
    return 0


def _segments_from_rows(rows: list[dict]) -> list[TranscriptionSegment]:
    return [
        TranscriptionSegment(
            start_time=r["start"],
            end_time=r["end"],
            text=r["text"],
            speaker=r["role"],
            confidence=float(r.get("confidence") or 0.85),
        )
        for r in rows
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-transcripts-only",
        action="store_true",
        help="Rebuild readable transcripts from evaluation/runs/hybrid caches (no inference).",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore prediction caches and re-run Community-1.",
    )
    args = parser.parse_args(argv)

    if args.export_transcripts_only:
        return export_transcripts_from_cache()

    from src.agents.transcription import _get_whisper_model

    model = _get_whisper_model()
    per_file = {}
    agg = {
        "heuristic_continuum_breaks": 0,
        "hybrid_continuum_breaks": 0,
        "heuristic_missed_acks": 0,
        "hybrid_missed_acks": 0,
        "hybrid_fallbacks": 0,
        "hybrid_acoustic_ok": 0,
    }

    for audio in SAMPLES:
        sid = audio.stem
        print(f"\n=== {sid} ===", flush=True)
        intake = run_intake(AudioInput(audio_data=audio.read_bytes(), filename=audio.name))
        wsegs, _ = model.transcribe(
            audio=str(intake.temp_file_path),
            beam_size=1,
            language="en",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        wsegs = list(wsegs)
        units = _sentence_units_from_whisper(wsegs)

        t_h = time.perf_counter()
        heur_segs = _run_heuristic(wsegs)
        heur_runtime = time.perf_counter() - t_h
        heur_labels = _label_sentences_from_segments(units, heur_segs)
        heur_cont = continuum_breaks(units, heur_labels)
        heur_acks = missed_short_acks(units, heur_labels)

        audio_path = Path(intake.temp_file_path)
        duration = _audio_duration_sec(audio_path)
        timeout = acoustic_timeout_sec(duration)
        cache = None if args.force_rerun else load_prediction_cache(sid)

        if cache is not None:
            print(f"  reusing cache {_cache_path(sid)}", flush=True)
            rows = cache["rows"]
            hy_segs = _segments_from_rows(rows)
            hy_runtime = 0.0
            fallback = bool(cache.get("fallback_activated"))
            fallback_reason = cache.get("fallback_reason")
            hy_diag = {
                "label_source": cache.get("label_source"),
                "acoustic_verified": cache.get("acoustic_verified"),
                "fallback_activated": fallback,
                "fallback_reason": fallback_reason,
                "role_mapping": cache.get("role_mapping"),
                "acoustic_timeout_sec": cache.get("acoustic_timeout_sec"),
                "audio_duration_sec": cache.get("audio_duration_sec"),
                "ambiguous_or_unmapped_utterances": cache.get("ambiguous_or_unmapped"),
                "timing_sec": cache.get("timing_sec"),
                "from_cache": True,
            }
        else:
            t_hy = time.perf_counter()
            fallback = False
            fallback_reason = None
            words, asr_spans = _words_and_spans_from_whisper(wsegs)
            try:
                rows_public, hy_diag = run_acoustic_diarization(
                    audio_path,
                    words,
                    asr_spans,
                    timeout_sec=timeout,
                )
                hy_segs = _segments_from_acoustic_dicts(rows_public)
                amb_n = hy_diag.get("ambiguous_or_unmapped_utterances", 0)
                hy_diag["ambiguous_or_unmapped_utterances"] = amb_n
                hy_diag["fallback_activated"] = False
                hy_diag["label_source"] = "acoustic"
                hy_diag["acoustic_verified"] = True
                rows = _rows_from_labeled(
                    hy_diag.get("labeled_payload") or [],
                    hy_diag.get("role_mapping"),
                )
            except Exception as exc:  # noqa: BLE001
                fallback = True
                fallback_reason = f"{type(exc).__name__}: {exc}"
                hy_segs, hy_diag = _run_heuristic_with_diagnostics(wsegs)
                hy_diag["fallback_activated"] = True
                hy_diag["fallback_reason"] = fallback_reason
                hy_diag["label_source"] = "heuristic_fallback"
                hy_diag["acoustic_verified"] = False
                rows = _rows_from_segments(hy_segs)
            hy_runtime = time.perf_counter() - t_hy
            hy_diag["acoustic_timeout_sec"] = round(timeout, 3)
            hy_diag["audio_duration_sec"] = round(duration, 3)

            save_prediction_cache(
                sid,
                {
                    "recording_id": sid,
                    "label_source": hy_diag.get("label_source"),
                    "acoustic_verified": hy_diag.get("acoustic_verified"),
                    "fallback_activated": fallback,
                    "fallback_reason": fallback_reason,
                    "role_mapping": hy_diag.get("role_mapping"),
                    "acoustic_timeout_sec": hy_diag.get("acoustic_timeout_sec"),
                    "audio_duration_sec": hy_diag.get("audio_duration_sec"),
                    "ambiguous_or_unmapped": hy_diag.get("ambiguous_or_unmapped_utterances"),
                    "timing_sec": hy_diag.get("timing_sec"),
                    "rows": rows,
                },
            )

        role_map_meta = hy_diag.get("role_mapping")
        if isinstance(role_map_meta, dict) and "mapping" in role_map_meta:
            role_map_meta = role_map_meta["mapping"]
        transcript_path = write_readable_transcript(
            sid,
            rows,
            meta={
                "label_source": hy_diag.get("label_source"),
                "acoustic_verified": hy_diag.get("acoustic_verified"),
                "fallback_activated": hy_diag.get("fallback_activated"),
                "role_mapping": role_map_meta,
            },
        )
        print(f"  transcript {transcript_path}", flush=True)

        hy_labels = _label_sentences_from_segments(units, hy_segs)
        hy_cont = continuum_breaks(units, hy_labels)
        hy_acks = missed_short_acks(units, hy_labels)

        entry = {
            "sentences": len(units),
            "transcript_path": str(transcript_path.relative_to(ROOT)),
            "prediction_cache": str(_cache_path(sid).relative_to(ROOT)),
            "heuristic": {
                "segments": len(heur_segs),
                "runtime_sec_diarize_only": round(heur_runtime, 3),
                "speaker_mix": dict(Counter(s.speaker for s in heur_segs)),
                "continuum_breaks": heur_cont,
                "missed_short_acks": heur_acks,
                "label_source": "heuristic",
            },
            "hybrid": {
                "segments": len(hy_segs),
                "runtime_sec_diarize_only": round(hy_runtime, 3),
                "speaker_mix": dict(Counter(s.speaker for s in hy_segs)),
                "continuum_breaks": hy_cont,
                "missed_short_acks": hy_acks,
                "fallback_activated": fallback,
                "fallback_reason": fallback_reason,
                "label_source": hy_diag.get("label_source"),
                "acoustic_verified": hy_diag.get("acoustic_verified"),
                "acoustic_timeout_sec": hy_diag.get("acoustic_timeout_sec"),
                "audio_duration_sec": hy_diag.get("audio_duration_sec"),
                "role_mapping": (hy_diag.get("role_mapping") if not fallback else None),
                "ambiguous_or_unmapped": hy_diag.get("ambiguous_or_unmapped_utterances"),
                "timing_sec": hy_diag.get("timing_sec"),
                "from_cache": bool(cache is not None),
            },
            "delta_continuum_breaks": hy_cont - heur_cont,
            "delta_missed_acks": hy_acks - heur_acks,
        }

        if sid == "sample_01" and ANN01.is_file():
            ann = json.loads(ANN01.read_text())
            sh = score_against_annotation(heur_segs, ann)
            sy = score_against_annotation(hy_segs, ann)
            entry["annotation_v2"] = {
                "heuristic": {
                    "correct": sh["correct"],
                    "clear": sh["clear_intervals"],
                    "accuracy": sh["accuracy"],
                    "confusions": sh["confusions"],
                    "errors": [d for d in sh["details"] if not d["correct"]],
                },
                "hybrid": {
                    "correct": sy["correct"],
                    "clear": sy["clear_intervals"],
                    "accuracy": sy["accuracy"],
                    "confusions": sy["confusions"],
                    "errors": [d for d in sy["details"] if not d["correct"]],
                },
                "baseline_reference_27_of_35": "prior dialogue-act heuristic report",
            }
            print(
                f"  ann.v2 heuristic {sh['correct']}/{sh['clear_intervals']} "
                f"hybrid {sy['correct']}/{sy['clear_intervals']}",
                flush=True,
            )

        agg["heuristic_continuum_breaks"] += heur_cont
        agg["hybrid_continuum_breaks"] += hy_cont
        agg["heuristic_missed_acks"] += heur_acks
        agg["hybrid_missed_acks"] += hy_acks
        if fallback:
            agg["hybrid_fallbacks"] += 1
        else:
            agg["hybrid_acoustic_ok"] += 1

        print(
            f"  continuum H={heur_cont} Hy={hy_cont}  acks H={heur_acks} Hy={hy_acks} "
            f"fallback={fallback} hy_runtime={hy_runtime:.1f}s timeout={timeout:.0f}s",
            flush=True,
        )
        per_file[sid] = entry

    report = {
        "method": {
            "heuristic": "sentence + dialogue-act + pattern-anchored FALLBACK",
            "hybrid": "Community-1 bounded subprocess → align/group/role; heuristic on timeout/error",
        },
        "annotation_note": (
            "Only sample_01 has listen-pass annotation.v2. Continuum/ack metrics on "
            "other files are structural proxies (same method as heuristic_all10 report)."
        ),
        "transcripts_dir": str(TRANSCRIPT_DIR.relative_to(ROOT)),
        "prediction_cache_dir": str(CACHE_DIR.relative_to(ROOT)),
        "timeout_policy": {
            "floor_sec": os.getenv("ACOUSTIC_TIMEOUT_FLOOR_SEC", "60"),
            "base_sec": os.getenv("ACOUSTIC_TIMEOUT_BASE_SEC", "30"),
            "per_audio_sec": os.getenv("ACOUSTIC_TIMEOUT_PER_AUDIO_SEC", "2.5"),
            "fixed": os.getenv("ACOUSTIC_TIMEOUT_SECONDS"),
        },
        "aggregate": {
            **agg,
            "continuum_reduction": agg["heuristic_continuum_breaks"]
            - agg["hybrid_continuum_breaks"],
            "ack_reduction": agg["heuristic_missed_acks"] - agg["hybrid_missed_acks"],
        },
        "per_file": per_file,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print("\n===== AGGREGATE =====")
    print(json.dumps(report["aggregate"], indent=2))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
