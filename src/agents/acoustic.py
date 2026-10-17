"""Community-1 acoustic diarization for the transcription agent.

Single public entry point: ``run_acoustic_diarization``. Internals cover
Community-1 inference (with hard timeout), word alignment, turn grouping,
role mapping, and diagnostics. Does not invent word timestamps or speaker IDs.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import re
import time
import traceback
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PIPELINE = "pyannote/speaker-diarization-community-1"
_BOUNDARY_COLLAR_SEC = 0.05
_MAX_INTRA_UTTERANCE_GAP_SEC = 0.75
_LAST_COMMUNITY1_DEVICE: str | None = None

_OPENING_AGENT_CUES = [
    re.compile(r"\bthank you for calling\b", re.IGNORECASE),
    re.compile(r"\bthanks for calling\b", re.IGNORECASE),
    re.compile(r"\bhow (?:may|can) I (?:help|assist) you\b", re.IGNORECASE),
    re.compile(r"\byou(?:'ve| have) reached\b", re.IGNORECASE),
]
# ponytail: skip "you've reached" (matches "once you've reached month three").
_SCENE_RESET_CUES = _OPENING_AGENT_CUES[:3]
_SCENE_PEEL_GAP_SEC = 3.0


class AcousticDiarizationError(RuntimeError):
    """Raised when local Community-1 cannot run. Callers must not fall back silently."""


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class AcousticInterval:
    start: float
    end: float
    speaker_id: str


@dataclass(frozen=True)
class AttributedWord:
    word: str
    start: float
    end: float
    speaker_id: str | None
    ambiguous: bool = False
    reason: str = ""


@dataclass(frozen=True)
class Utterance:
    start: float
    end: float
    text: str
    speaker_id: str | None
    ambiguous: bool = False
    confidence: float = 0.0
    split_from_mixed_asr: bool = False
    words: tuple[AttributedWord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RoleMapping:
    mapping: dict[str, str]
    method: str
    notes: str = ""


def _hf_token() -> str | None:
    return (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or None
    )


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _select_inference_device():
    """Prefer CUDA, then Apple MPS, then CPU."""
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _pipeline_parameter_device_types(pipeline) -> set[str]:
    """Return torch device types (cpu/cuda/mps) for nn.Module parameters in the pipeline."""
    from torch import nn

    found: set[str] = set()
    seen: set[int] = set()

    def walk(obj) -> None:
        oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)
        if isinstance(obj, nn.Module):
            for param in obj.parameters(recurse=False):
                found.add(param.device.type)
            for child in obj.children():
                walk(child)
            return
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)
            return
        if isinstance(obj, (list, tuple)):
            for value in obj:
                walk(value)
            return
        state = getattr(obj, "__dict__", None)
        if state:
            for key, value in state.items():
                if key.startswith("__"):
                    continue
                walk(value)

    walk(pipeline)
    return found


@lru_cache(maxsize=1)
def _load_community1(model_id: str):
    global _LAST_COMMUNITY1_DEVICE
    token = _hf_token()
    if not token or not token.strip():
        raise AcousticDiarizationError(
            "HF_TOKEN is not set. Add it to .env and accept terms at "
            "https://huggingface.co/pyannote/speaker-diarization-community-1"
        )
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise AcousticDiarizationError(
            "pyannote.audio is not installed. pip install pyannote.audio"
        ) from exc

    try:
        pipeline = Pipeline.from_pretrained(model_id, token=token.strip())
    except Exception as exc:
        raise AcousticDiarizationError(
            f"Failed to load {model_id!r} locally. Accept gated model terms at "
            "https://huggingface.co/pyannote/speaker-diarization-community-1 "
            f"Underlying error: {exc}"
        ) from exc

    if pipeline is None:
        raise AcousticDiarizationError(
            f"Pipeline.from_pretrained({model_id!r}) returned None "
            "(usually gated terms not accepted)."
        )

    device = _select_inference_device()
    try:
        pipeline.to(device)
    except Exception as exc:
        raise AcousticDiarizationError(
            f"Failed to move Community-1 pipeline to device {device}: {exc}"
        ) from exc

    param_types = _pipeline_parameter_device_types(pipeline)
    print(
        f"[acoustic] Community-1 device selected={device} "
        f"parameter_device_types={sorted(param_types) or ['<none>']}"
    )
    if not param_types:
        raise AcousticDiarizationError(
            f"Community-1 moved to {device} but no model parameters were found to verify."
        )
    unexpected = sorted(t for t in param_types if t != device.type)
    if unexpected:
        raise AcousticDiarizationError(
            f"Community-1 pipeline.to({device}) did not stick: "
            f"expected parameter device type {device.type!r}, found {sorted(param_types)}"
        )

    _LAST_COMMUNITY1_DEVICE = str(device)
    return pipeline


def _iter_turns(diarization):
    if hasattr(diarization, "itertracks"):
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            yield float(turn.start), float(turn.end), str(speaker)
        return
    for turn, speaker in diarization:
        yield float(turn.start), float(turn.end), str(speaker)


def _load_mono_16k_waveform(
    path: Path,
    *,
    offset_sec: float = 0.0,
    duration_sec: float | None = None,
):
    """Load audio as torch waveform for pyannote (avoids torchcodec/ffmpeg path issues)."""
    import librosa
    import torch

    samples, _sr = librosa.load(
        str(path),
        sr=16000,
        mono=True,
        offset=max(0.0, float(offset_sec)),
        duration=duration_sec,
    )
    waveform = torch.from_numpy(samples.astype("float32")).unsqueeze(0)
    return {"waveform": waveform, "sample_rate": 16000}


def run_community1(
    audio_path: str | Path,
    *,
    num_speakers: int | None = 2,
    offset_sec: float = 0.0,
    duration_sec: float | None = None,
) -> tuple[list[AcousticInterval], dict]:
    """Local Community-1 → speaker intervals. Prefer exclusive diarization when present.

    Returns (intervals, timing_sec) for lightweight performance diagnostics.
    ``offset_sec`` / ``duration_sec`` crop the file (slice times are shifted back
    onto the original timeline).
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    model_id = os.getenv("PYANNOTE_DIARIZATION_MODEL", _DEFAULT_PIPELINE)
    if "precision-2" in model_id:
        raise AcousticDiarizationError(
            "Refusing hosted Precision-2. Use pyannote/speaker-diarization-community-1."
        )

    t0 = time.perf_counter()
    pipeline = _load_community1(model_id)
    pipeline_init_sec = time.perf_counter() - t0
    offset = max(0.0, float(offset_sec))

    kwargs = {"num_speakers": num_speakers} if num_speakers is not None else {}
    try:
        # Pass in-memory waveform (documented pyannote API) so inference does not
        # depend on torchcodec + system FFmpeg shared libraries.
        t1 = time.perf_counter()
        waveform = _load_mono_16k_waveform(path, offset_sec=offset, duration_sec=duration_sec)
        audio_load_sec = time.perf_counter() - t1
        t2 = time.perf_counter()
        output = pipeline(waveform, **kwargs)
        inference_sec = time.perf_counter() - t2
    except Exception as exc:
        raise AcousticDiarizationError(f"Local Community-1 inference failed: {exc}") from exc

    if hasattr(output, "exclusive_speaker_diarization"):
        diarization = output.exclusive_speaker_diarization
    elif hasattr(output, "speaker_diarization"):
        diarization = output.speaker_diarization
    else:
        diarization = output

    intervals = [
        AcousticInterval(start=s + offset, end=e + offset, speaker_id=spk)
        for s, e, spk in _iter_turns(diarization)
    ]
    intervals.sort(key=lambda iv: (iv.start, iv.end))
    if not intervals:
        raise AcousticDiarizationError("Community-1 returned no speaker intervals.")
    timing = {
        "community1_device": _LAST_COMMUNITY1_DEVICE,
        "community1_pipeline_init": round(pipeline_init_sec, 3),
        "community1_audio_load": round(audio_load_sec, 3),
        "community1_inference": round(inference_sec + audio_load_sec, 3),
        "community1_pipeline_forward": round(inference_sec, 3),
    }
    return intervals, timing


def align_words_to_speakers(
    words: list[WordTiming] | tuple[WordTiming, ...],
    intervals: list[AcousticInterval] | tuple[AcousticInterval, ...],
    *,
    boundary_collar_sec: float = _BOUNDARY_COLLAR_SEC,
) -> list[AttributedWord]:
    """Assign acoustic speaker IDs by time overlap. Never invents timestamps."""
    if not words:
        return []

    ordered = sorted(intervals, key=lambda iv: (iv.start, iv.end))
    out: list[AttributedWord] = []

    for word in words:
        if word.end < word.start:
            out.append(
                AttributedWord(word.word, word.start, word.end, None, True, "invalid_timestamps")
            )
            continue

        overlaps = [
            (_overlap(word.start, word.end, iv.start, iv.end), iv)
            for iv in ordered
            if _overlap(word.start, word.end, iv.start, iv.end) > 0
        ]
        if not overlaps:
            out.append(
                AttributedWord(word.word, word.start, word.end, None, True, "no_acoustic_overlap")
            )
            continue

        overlaps.sort(key=lambda x: x[0], reverse=True)
        best_ov, best_iv = overlaps[0]
        mid = 0.5 * (word.start + word.end)

        near_boundary = False
        for iv in ordered:
            for edge in (iv.start, iv.end):
                if abs(mid - edge) > boundary_collar_sec:
                    continue
                others = [
                    o
                    for o in ordered
                    if o.speaker_id != iv.speaker_id
                    and (
                        abs(mid - o.start) <= boundary_collar_sec
                        or abs(mid - o.end) <= boundary_collar_sec
                        or _overlap(word.start, word.end, o.start, o.end) > 0
                    )
                ]
                if others:
                    near_boundary = True
                    break
            if near_boundary:
                break

        reason = "overlap_majority"
        ambiguous = False
        speaker_id: str | None = best_iv.speaker_id

        if len(overlaps) >= 2 and overlaps[1][0] >= 0.4 * best_ov:
            ambiguous = True
            reason = "overlapping_speech"
            speaker_id = None
        elif near_boundary:
            ambiguous = True
            reason = "boundary_collar"

        out.append(AttributedWord(word.word, word.start, word.end, speaker_id, ambiguous, reason))
    return out


def collect_boundary_bleed_candidates(
    words: list[WordTiming] | tuple[WordTiming, ...],
    intervals: list[AcousticInterval] | tuple[AcousticInterval, ...],
    attributed: list[AttributedWord] | tuple[AttributedWord, ...],
) -> list[dict]:
    """Flag timestamp-bleed suspects: multi-speaker word overlap where acoustic
    intervals themselves do not overlap (gap between turns).

    Does **not** reassign. Preserves word timestamps and per-interval overlaps.
    Records a *hypothetical* clamp-after-earlier-turn label for later review only.
    """
    ordered = sorted(intervals, key=lambda iv: (iv.start, iv.end))
    candidates: list[dict] = []

    for word, attr in zip(words, attributed):
        if attr.reason != "overlapping_speech":
            continue

        overlap_rows: list[dict] = []
        for iv in ordered:
            ov = _overlap(word.start, word.end, iv.start, iv.end)
            if ov <= 0:
                continue
            overlap_rows.append(
                {
                    "speaker_id": iv.speaker_id,
                    "interval_start": round(iv.start, 4),
                    "interval_end": round(iv.end, 4),
                    "overlap_sec": round(ov, 4),
                    "overlap_frac_of_word": round(ov / max(word.end - word.start, 1e-9), 4),
                }
            )
        if len(overlap_rows) < 2:
            continue

        # Acoustic intervals that hit this word — check for a non-overlapping pair.
        hit_ivs = [iv for iv in ordered if _overlap(word.start, word.end, iv.start, iv.end) > 0]
        earlier: AcousticInterval | None = None
        later: AcousticInterval | None = None
        for i, a_iv in enumerate(hit_ivs):
            for b_iv in hit_ivs[i + 1 :]:
                if a_iv.end <= b_iv.start:
                    earlier, later = a_iv, b_iv
                    break
                if b_iv.end <= a_iv.start:
                    earlier, later = b_iv, a_iv
                    break
            if earlier is not None:
                break
        if earlier is None or later is None:
            # Genuine overlapping acoustic intervals — not this failure mode.
            continue

        overlap_rows.sort(key=lambda r: r["overlap_sec"], reverse=True)
        majority_speaker = overlap_rows[0]["speaker_id"]

        # Hypothetical clamp: drop mass inside the earlier turn; keep [earlier.end, word.end].
        clamp_start = earlier.end
        clamp_end = word.end
        clamp_overlaps = []
        for iv in ordered:
            ov = _overlap(clamp_start, clamp_end, iv.start, iv.end)
            if ov > 0:
                clamp_overlaps.append(
                    {
                        "speaker_id": iv.speaker_id,
                        "interval_start": round(iv.start, 4),
                        "interval_end": round(iv.end, 4),
                        "overlap_sec": round(ov, 4),
                    }
                )
        clamp_overlaps.sort(key=lambda r: r["overlap_sec"], reverse=True)
        hypothetical_clamp_speaker = clamp_overlaps[0]["speaker_id"] if clamp_overlaps else None

        gap_sec = round(later.start - earlier.end, 4)
        candidates.append(
            {
                "word": word.word,
                "start": round(word.start, 4),
                "end": round(word.end, 4),
                "duration_sec": round(max(word.end - word.start, 0.0), 4),
                "align_reason": attr.reason,
                "preserved_overlaps": overlap_rows,
                "earlier_interval": {
                    "speaker_id": earlier.speaker_id,
                    "start": round(earlier.start, 4),
                    "end": round(earlier.end, 4),
                },
                "later_interval": {
                    "speaker_id": later.speaker_id,
                    "start": round(later.start, 4),
                    "end": round(later.end, 4),
                },
                "inter_speaker_gap_sec": gap_sec,
                "majority_overlap_speaker": majority_speaker,
                "hypothetical_clamp_speaker": hypothetical_clamp_speaker,
                "hypothetical_clamp_window": {
                    "start": round(clamp_start, 4),
                    "end": round(clamp_end, 4),
                },
                "clamp_vs_majority_disagree": (
                    hypothetical_clamp_speaker is not None
                    and hypothetical_clamp_speaker != majority_speaker
                ),
                "auto_reassigned": False,
                "note": (
                    "Flag only. Clamp hypothesis assumes earlier-turn overlap is "
                    "timestamp bleed — not established; do not auto-apply."
                ),
            }
        )
    return candidates


def _speakers_in_span(attributed: list[AttributedWord], start: float, end: float) -> set[str]:
    found: set[str] = set()
    for w in attributed:
        if w.speaker_id and _overlap(w.start, w.end, start, end) > 0:
            found.add(w.speaker_id)
    return found


def _word_hits_interval(word: AttributedWord, iv: AcousticInterval) -> float:
    """Overlap seconds, or 1.0 for a point timestamp contained in the interval."""
    if word.end > word.start:
        return _overlap(word.start, word.end, iv.start, iv.end)
    # Zero/negative duration Whisper glitch: treat as a point.
    if iv.start <= word.start <= iv.end:
        return 1.0
    return 0.0


def _group_consecutive_speakers(
    attributed_words: list[AttributedWord],
    *,
    max_gap_sec: float,
    asr_spans: list[tuple[float, float]] | None,
) -> list[Utterance]:
    """Legacy baseline: consecutive same-speaker words; Ambiguous words hard-split."""
    if not attributed_words:
        return []

    mixed_spans: list[tuple[float, float]] = []
    if asr_spans:
        for a0, a1 in asr_spans:
            if len(_speakers_in_span(attributed_words, a0, a1)) >= 2:
                mixed_spans.append((a0, a1))

    def in_mixed(t0: float, t1: float) -> bool:
        return any(max(t0, a0) < min(t1, a1) for a0, a1 in mixed_spans)

    utterances: list[Utterance] = []
    current: list[AttributedWord] = []
    current_spk: str | None = None

    def flush() -> None:
        nonlocal current, current_spk
        if not current:
            return
        ambiguous = any(w.ambiguous for w in current) or current_spk is None
        conf = 0.25 if current_spk is None else (0.35 if ambiguous else 0.85)
        utterances.append(
            Utterance(
                start=current[0].start,
                end=current[-1].end,
                text=" ".join(w.word for w in current).strip(),
                speaker_id=current_spk,
                ambiguous=ambiguous,
                confidence=conf,
                split_from_mixed_asr=in_mixed(current[0].start, current[-1].end),
                words=tuple(current),
            )
        )
        current = []
        current_spk = None

    for word in attributed_words:
        if word.ambiguous and word.speaker_id is None:
            flush()
            utterances.append(
                Utterance(
                    start=word.start,
                    end=word.end,
                    text=word.word,
                    speaker_id=None,
                    ambiguous=True,
                    confidence=0.2,
                    split_from_mixed_asr=in_mixed(word.start, word.end),
                    words=(word,),
                )
            )
            continue

        if current and (
            word.speaker_id != current_spk or (word.start - current[-1].end) > max_gap_sec
        ):
            flush()

        if not current:
            current_spk = word.speaker_id
        current.append(word)

    flush()
    return utterances


def _hit_turns_genuinely_overlap(
    hits: list[tuple[int, AcousticInterval, float]],
) -> bool:
    """True when two hit acoustic intervals overlap each other (real crosstalk)."""
    ivs = [iv for _, iv, _ in hits]
    for i, a in enumerate(ivs):
        for b in ivs[i + 1 :]:
            if _overlap(a.start, a.end, b.start, b.end) > 0:
                return True
    return False


def _clear_neighbor_speakers(
    attributed: list[AttributedWord],
    index: int,
    *,
    max_gap_sec: float,
) -> tuple[str | None, str | None]:
    """Nearest clear left/right speaker_ids within ``max_gap_sec``, else None."""
    left_id = None
    for j in range(index - 1, -1, -1):
        w = attributed[j]
        if w.ambiguous or w.speaker_id is None:
            continue
        if attributed[index].start - w.end > max_gap_sec:
            break
        left_id = w.speaker_id
        break
    right_id = None
    for j in range(index + 1, len(attributed)):
        w = attributed[j]
        if w.ambiguous or w.speaker_id is None:
            continue
        if w.start - attributed[index].end > max_gap_sec:
            break
        right_id = w.speaker_id
        break
    return left_id, right_id


def _unanimous_asr_clear_speaker(
    attributed: list[AttributedWord],
    index: int,
    asr_spans: list[tuple[float, float]] | None,
) -> str | None:
    """If clear words in the same ASR span agree on one speaker, return it.

    Uses the ASR span with maximum temporal overlap with the word (not the first
    nick), so boundary-bleed words attach to their primary phrase span.
    Clear peers are counted only when a majority of their duration lies in the
    span, so a tiny nick from an adjacent phrase cannot spoil unanimity.
    """
    if not asr_spans:
        return None
    word = attributed[index]
    word_end = max(word.end, word.start + 1e-6)
    best_span: tuple[float, float] | None = None
    best_ov = 0.0
    for a0, a1 in asr_spans:
        if word.end <= word.start and a0 <= word.start <= a1:
            ov = 1.0
        else:
            ov = _overlap(word.start, word_end, a0, a1)
        if ov > best_ov:
            best_ov = ov
            best_span = (a0, a1)
    if best_span is None or best_ov <= 0:
        return None
    a0, a1 = best_span
    speakers: set[str] = set()
    for i, w in enumerate(attributed):
        if i == index:
            continue
        if w.ambiguous or w.speaker_id is None:
            continue
        w_end = max(w.end, w.start + 1e-6)
        dur = w_end - w.start
        ov = _overlap(w.start, w_end, a0, a1)
        if w.end <= w.start and a0 <= w.start <= a1:
            ov = 1.0
            dur = 1.0
        if dur <= 0 or ov / dur < 0.5:
            continue
        speakers.add(w.speaker_id)
    if len(speakers) == 1:
        return next(iter(speakers))
    return None


def _resolve_ambiguous_turn(
    word: AttributedWord,
    index: int,
    hits: list[tuple[int, AcousticInterval, float]],
    attributed: list[AttributedWord],
    turns: list[AcousticInterval],
    *,
    asr_spans: list[tuple[float, float]] | None,
    max_gap_sec: float,
) -> tuple[int, AcousticInterval, str] | None:
    """Choose a turn index for an ambiguous word, or None if unresolved.

    Returns (turn_index, interval, reason). Never mutates timestamps.
    """
    speaker_ids_hit = {iv.speaker_id for _, iv, _ in hits}

    # Real overlapping speech between acoustic turns — do not invent.
    if len(hits) >= 2 and _hit_turns_genuinely_overlap(hits):
        return None

    if len(speaker_ids_hit) == 1 and hits:
        best_i, best_iv, _ = max(hits, key=lambda h: h[2])
        return best_i, best_iv, "single_turn_containment"

    left_id, right_id = _clear_neighbor_speakers(attributed, index, max_gap_sec=max_gap_sec)
    asr_id = _unanimous_asr_clear_speaker(attributed, index, asr_spans)

    def _best_hit_for(speaker_id: str) -> tuple[int, AcousticInterval, float] | None:
        matching = [h for h in hits if h[1].speaker_id == speaker_id]
        if not matching:
            return None
        return max(matching, key=lambda h: h[2])

    def _nearest_turn_for(speaker_id: str) -> tuple[int, AcousticInterval] | None:
        candidates = [(i, iv) for i, iv in enumerate(turns) if iv.speaker_id == speaker_id]
        if not candidates:
            return None

        def gap(iv: AcousticInterval) -> float:
            if word.end < iv.start:
                return iv.start - word.end
            if word.start > iv.end:
                return word.start - iv.end
            return 0.0

        best_i, best_iv = min(candidates, key=lambda t: gap(t[1]))
        if gap(best_iv) > max_gap_sec:
            return None
        return best_i, best_iv

    # Same-ASR clear words unanimously continue one speaker.
    if asr_id is not None:
        hit = _best_hit_for(asr_id)
        if hit is not None:
            return hit[0], hit[1], "asr_span_continuation"
        # No hit on that speaker: only continue if nothing else was hit (gap/bleed
        # entirely outside turns) — competing hit speakers stay unresolved.
        if not speaker_ids_hit:
            nearest = _nearest_turn_for(asr_id)
            if nearest is not None:
                return nearest[0], nearest[1], "asr_span_continuation"

    # Align already proposed an ID (e.g. boundary_collar) and it is among the hits,
    # with at least one adjacent clear word agreeing — continuation into that turn.
    if (
        word.speaker_id is not None
        and word.speaker_id in speaker_ids_hit
        and (left_id == word.speaker_id or right_id == word.speaker_id)
    ):
        hit = _best_hit_for(word.speaker_id)
        if hit is not None:
            return hit[0], hit[1], "align_id_neighbor_continuation"

    # Both clear neighbors agree on S (in-turn island).
    if left_id is not None and left_id == right_id:
        hit = _best_hit_for(left_id)
        if hit is not None:
            return hit[0], hit[1], "neighbor_continuity"
        # No direct hit: attach to nearest S turn when no competing speaker was hit.
        if not (speaker_ids_hit - {left_id}):
            nearest = _nearest_turn_for(left_id)
            if nearest is not None:
                return nearest[0], nearest[1], "neighbor_continuity"
        return None

    # Single-sided continuation at a turn edge (neighbors may differ or one missing).
    if left_id is not None and right_id is None:
        hit = _best_hit_for(left_id)
        if hit is not None:
            return hit[0], hit[1], "left_neighbor_continuation"
    if right_id is not None and left_id is None:
        hit = _best_hit_for(right_id)
        if hit is not None:
            return hit[0], hit[1], "right_neighbor_continuation"

    # Different neighbors at a bleed boundary: only resolve when ASR unanimity
    # already handled above; otherwise competing continuations → unresolved.
    return None


def _group_by_acoustic_turns(
    attributed_words: list[AttributedWord],
    intervals: list[AcousticInterval] | tuple[AcousticInterval, ...],
    *,
    asr_spans: list[tuple[float, float]] | None,
) -> tuple[list[Utterance], list[dict]]:
    """Group by Community-1 turns; absorb isolated ambiguous words when evidence is clear.

    Clear align assignments (``ambiguous=False`` with a ``speaker_id``) are placed on
    the matching speaker turn and are not discarded by tiny multi-turn overlaps.
    Ambiguous words may be attributed to an adjacent turn using ASR-span / neighbor
    continuation when acoustic turns do not genuinely overlap. Original word
    timestamps and ambiguous flags are preserved; inferred assignment is diagnostics-only.
    """
    turns = sorted(intervals, key=lambda iv: (iv.start, iv.end))
    if not attributed_words:
        return [], []

    buckets: list[list[AttributedWord]] = [[] for _ in turns]
    unresolved: list[AttributedWord] = []
    absorptions: list[dict] = []

    def _place_on_speaker_turn(word: AttributedWord, hits: list) -> bool:
        matching = [h for h in hits if h[1].speaker_id == word.speaker_id]
        if not matching:
            return False
        best_i = max(matching, key=lambda h: h[2])[0]
        buckets[best_i].append(word)
        return True

    for index, word in enumerate(attributed_words):
        hits = [
            (i, iv, _word_hits_interval(word, iv))
            for i, iv in enumerate(turns)
            if _word_hits_interval(word, iv) > 0
        ]

        # Preserve unambiguous upstream assignments.
        if not word.ambiguous and word.speaker_id is not None:
            if not _place_on_speaker_turn(word, hits):
                unresolved.append(word)
            continue

        if not word.ambiguous:
            unresolved.append(word)
            continue

        # Ambiguous path: attempt general continuation / containment resolution.
        resolved = _resolve_ambiguous_turn(
            word,
            index,
            hits,
            attributed_words,
            turns,
            asr_spans=asr_spans,
            max_gap_sec=_MAX_INTRA_UTTERANCE_GAP_SEC,
        )
        if resolved is not None:
            best_i, best_iv, reason = resolved
            buckets[best_i].append(word)
            absorptions.append(
                {
                    "word": word.word,
                    "start": round(word.start, 4),
                    "end": round(word.end, 4),
                    "original_ambiguous": True,
                    "original_reason": word.reason,
                    "original_speaker_id": word.speaker_id,
                    "absorbed_into_speaker_id": best_iv.speaker_id,
                    "turn_start": round(best_iv.start, 4),
                    "turn_end": round(best_iv.end, 4),
                    "absorption": reason,
                }
            )
            continue

        unresolved.append(word)

    mixed_spans: list[tuple[float, float]] = []
    if asr_spans:
        for a0, a1 in asr_spans:
            if len(_speakers_in_span(attributed_words, a0, a1)) >= 2:
                mixed_spans.append((a0, a1))

    def in_mixed(t0: float, t1: float) -> bool:
        return any(max(t0, a0) < min(t1, a1) for a0, a1 in mixed_spans)

    utterances: list[Utterance] = []

    for turn, bucket in zip(turns, buckets):
        if not bucket:
            continue
        bucket = sorted(bucket, key=lambda w: (w.start, w.end))
        utterances.append(
            Utterance(
                start=bucket[0].start,
                end=bucket[-1].end,
                text=" ".join(w.word for w in bucket).strip(),
                speaker_id=turn.speaker_id,
                ambiguous=False,
                confidence=0.85,
                split_from_mixed_asr=in_mixed(bucket[0].start, bucket[-1].end),
                words=tuple(bucket),
            )
        )

    for word in unresolved:
        utterances.append(
            Utterance(
                start=word.start,
                end=word.end,
                text=word.word,
                speaker_id=None,
                ambiguous=True,
                confidence=0.2,
                split_from_mixed_asr=in_mixed(word.start, word.end),
                words=(word,),
            )
        )

    utterances.sort(key=lambda u: (u.start, u.end))
    return utterances, absorptions


def group_utterances(
    attributed_words: list[AttributedWord],
    *,
    intervals: list[AcousticInterval] | tuple[AcousticInterval, ...] | None = None,
    max_gap_sec: float = _MAX_INTRA_UTTERANCE_GAP_SEC,
    asr_spans: list[tuple[float, float]] | None = None,
    turn_first: bool = True,
) -> tuple[list[Utterance], list[dict]]:
    """Group words into utterances.

    Default (``turn_first=True`` with ``intervals``): Community-1 turns are primary;
    isolated ambiguous words may be absorbed when continuation evidence is clear.
    Baseline (``turn_first=False``): legacy consecutive-speaker hard splits.
    """
    if turn_first and intervals is not None:
        return _group_by_acoustic_turns(attributed_words, intervals, asr_spans=asr_spans)
    return (
        _group_consecutive_speakers(attributed_words, max_gap_sec=max_gap_sec, asr_spans=asr_spans),
        [],
    )


def map_roles(
    utterances: list[Utterance],
    *,
    opening_window_sec: float = 45.0,
) -> RoleMapping:
    """Map acoustic IDs → Agent/Customer. Does not rewrite which ID owns which words."""
    speaker_ids = sorted({u.speaker_id for u in utterances if u.speaker_id is not None})
    if not speaker_ids:
        return RoleMapping({}, "empty", "No acoustic speakers.")
    if len(speaker_ids) == 1:
        only = speaker_ids[0]
        return RoleMapping(
            {only: "Agent"},
            "single_speaker_default",
            "Only one acoustic speaker; labeled Agent by call-center prior.",
        )

    cue_votes = {s: 0 for s in speaker_ids}
    for u in utterances:
        if u.speaker_id is None or u.ambiguous or u.start > opening_window_sec:
            continue
        if any(p.search(u.text) for p in _OPENING_AGENT_CUES):
            cue_votes[u.speaker_id] += 1

    extended = False
    if max(cue_votes.values()) == 0:
        # ponytail: 45s gate first; scan later only when empty. Per-scenario remap if roleplays concatenate.
        extended = True
        for u in utterances:
            if u.speaker_id is None or u.ambiguous:
                continue
            if any(p.search(u.text) for p in _OPENING_AGENT_CUES):
                cue_votes[u.speaker_id] += 1

    if max(cue_votes.values()) > 0:
        agent_id = max(cue_votes, key=lambda s: cue_votes[s])
        note = (
            f"No cues in first {opening_window_sec}s; later cues favored {agent_id}: {cue_votes}"
            if extended
            else f"Opening cues favored {agent_id}: {cue_votes}"
        )
        return RoleMapping(
            {s: ("Agent" if s == agent_id else "Customer") for s in speaker_ids},
            "opening_greeting_cues",
            note,
        )

    for u in sorted(utterances, key=lambda x: x.start):
        if u.speaker_id is None or u.ambiguous:
            continue
        agent_id = u.speaker_id
        return RoleMapping(
            {s: ("Agent" if s == agent_id else "Customer") for s in speaker_ids},
            "first_reliable_speaker_as_agent",
            f"First reliable speaker {agent_id} → Agent (not by SPEAKER_XX index).",
        )

    agent_id = speaker_ids[0]
    return RoleMapping(
        {s: ("Agent" if s == agent_id else "Customer") for s in speaker_ids},
        "lexicographic_fallback",
        "All utterances ambiguous; lexicographic speaker_id → Agent.",
    )


def label_utterances(
    utterances: list[Utterance],
    role_mapping: RoleMapping,
) -> list[tuple[Utterance, str | None]]:
    """Pair utterances with Agent/Customer (None if unknown / unmapped)."""
    return [
        (u, None if u.speaker_id is None else role_mapping.mapping.get(u.speaker_id))
        for u in utterances
    ]


def _has_scene_reset_cue(text: str) -> bool:
    return any(p.search(text or "") for p in _SCENE_RESET_CUES)


def split_roleplay_scenes(
    utterances: list[Utterance],
    mapping: RoleMapping,
) -> list[list[Utterance]]:
    """Start a new scene when a Customer-mapped ID hits a fresh opening greeting.

    Walks back a short same-speaker tail so a split ASR greeting stays in the new scene.
    """
    if not utterances:
        return []
    scenes: list[list[Utterance]] = []
    current: list[Utterance] = []
    for u in utterances:
        role = None if u.speaker_id is None else mapping.mapping.get(u.speaker_id)
        already_in_new_scene = current and all(x.speaker_id == u.speaker_id for x in current)
        if (
            current
            and _has_scene_reset_cue(u.text)
            and role == "Customer"
            and not already_in_new_scene
        ):
            peeled = [u]
            while (
                current
                and current[-1].speaker_id == u.speaker_id
                and u.start - current[-1].end <= _SCENE_PEEL_GAP_SEC
            ):
                peeled.append(current.pop())
            peeled.reverse()
            if current:
                scenes.append(current)
            current = peeled
            continue
        current.append(u)
    if current:
        scenes.append(current)
    return scenes or [utterances]


def _collapsed_roleplay_scene(scene: list[Utterance]) -> bool:
    ids = {u.speaker_id for u in scene if u.speaker_id}
    return len(ids) == 1 and len(scene) >= 4 and any(_has_scene_reset_cue(u.text) for u in scene)


def label_utterances_by_scene(
    utterances: list[Utterance],
) -> tuple[list[tuple[Utterance, str | None]], list[RoleMapping]]:
    """map_roles per concatenated roleplay. Global mapping still used to find splits."""
    if not utterances:
        return [], []
    global_map = map_roles(utterances)
    scenes = split_roleplay_scenes(utterances, global_map)
    labeled: list[tuple[Utterance, str | None]] = []
    maps: list[RoleMapping] = []
    for scene in scenes:
        mapping = map_roles(scene)
        maps.append(mapping)
        labeled.extend(label_utterances(scene, mapping))
    return labeled, maps


def build_role_segments(
    audio_path: str | Path,
    words: list[WordTiming],
    asr_spans: list[tuple[float, float]],
    *,
    turn_first: bool = True,
) -> tuple[list[tuple[Utterance, str | None]], dict]:
    """Full acoustic path: Community-1 → align → turn-first group → role map.

    Returns (labeled utterances, diagnostics). Raises AcousticDiarizationError on failure.
    Boundary-bleed candidates are flagged only (no auto reassignment / clamping).
    """
    intervals, c1_timing = run_community1(audio_path, num_speakers=2)
    t_post = time.perf_counter()
    attributed = align_words_to_speakers(words, intervals)
    bleed_candidates = collect_boundary_bleed_candidates(words, intervals, attributed)
    utterances, absorptions = group_utterances(
        attributed,
        intervals=intervals,
        asr_spans=asr_spans,
        turn_first=turn_first,
    )
    global_map = map_roles(utterances)
    scenes = split_roleplay_scenes(utterances, global_map)
    labeled: list[tuple[Utterance, str | None]] = []
    scene_maps: list[RoleMapping] = []
    slice_retries = 0
    for scene in scenes:
        scene_utts = scene
        if _collapsed_roleplay_scene(scene):
            t0 = scene[0].start
            t1 = max(u.end for u in scene)
            try:
                sub_iv, _sub_t = run_community1(
                    audio_path,
                    num_speakers=2,
                    offset_sec=t0,
                    duration_sec=max(t1 - t0, 0.1),
                )
                sub_words = [w for w in words if _overlap(w.start, max(w.end, w.start), t0, t1) > 0]
                sub_spans = [
                    (max(a0, t0), min(a1, t1)) for a0, a1 in asr_spans if max(a0, t0) < min(a1, t1)
                ]
                sub_attr = align_words_to_speakers(sub_words, sub_iv)
                scene_utts, extra_abs = group_utterances(
                    sub_attr,
                    intervals=sub_iv,
                    asr_spans=sub_spans,
                    turn_first=turn_first,
                )
                absorptions.extend(extra_abs)
                slice_retries += 1
            except Exception:  # noqa: BLE001
                scene_utts = scene
        mapping = map_roles(scene_utts)
        scene_maps.append(mapping)
        labeled.extend(label_utterances(scene_utts, mapping))
    roles = scene_maps[0] if scene_maps else global_map
    align_group_role_sec = time.perf_counter() - t_post
    unresolved_ambiguous = sum(1 for u, _role in labeled if u.ambiguous or u.speaker_id is None)
    diagnostics = {
        "backend": "acoustic",
        "model": os.getenv("PYANNOTE_DIARIZATION_MODEL", _DEFAULT_PIPELINE),
        "acoustic_intervals": len(intervals),
        "acoustic_speakers": sorted({iv.speaker_id for iv in intervals}),
        "attributed_words": len(attributed),
        "ambiguous_words": sum(1 for w in attributed if w.ambiguous),
        "turn_first_grouping": turn_first,
        "absorbed_ambiguous_words": absorptions,
        "absorbed_ambiguous_count": len(absorptions),
        "boundary_bleed_candidates": bleed_candidates,
        "boundary_bleed_candidate_count": len(bleed_candidates),
        "utterances": len(labeled),
        "unresolved_ambiguous_utterances": unresolved_ambiguous,
        "mixed_asr_splits": sum(1 for u, _r in labeled if u.split_from_mixed_asr),
        "role_mapping": {
            "method": ("per_scene_opening_cues" if len(scene_maps) > 1 else roles.method),
            "mapping": roles.mapping,
            "notes": roles.notes,
            "scenes": [
                {
                    "method": m.method,
                    "mapping": m.mapping,
                    "notes": m.notes,
                }
                for m in scene_maps
            ],
            "collapsed_slice_retries": slice_retries,
        },
        "schema_limitation": (
            "TranscriptionSegment.speaker is a required string. Ambiguous/unmapped "
            "utterances should be emitted as speaker='Ambiguous' with confidence<=0.3."
        ),
        "timing_sec": {
            **c1_timing,
            "align_group_role": round(align_group_role_sec, 3),
        },
    }
    return labeled, diagnostics


# ---------------------------------------------------------------------------
# Bounded execution (subprocess + hard timeout) and public entry point
# ---------------------------------------------------------------------------

# Debug UI / callers can request cancel; terminate the active Community-1 child.
_CANCEL_REQUESTED = False
_ACTIVE_ACOUSTIC_PROC: mp.Process | None = None


def request_acoustic_cancel() -> None:
    """Best-effort stop: kill the active bounded acoustic worker if any."""
    global _CANCEL_REQUESTED
    _CANCEL_REQUESTED = True
    proc = _ACTIVE_ACOUSTIC_PROC
    if proc is not None and proc.is_alive():
        proc.terminate()
        proc.join(2)
        if proc.is_alive():
            proc.kill()
            proc.join(1)


def clear_acoustic_cancel() -> None:
    global _CANCEL_REQUESTED
    _CANCEL_REQUESTED = False


def acoustic_timeout_sec(audio_duration_sec: float) -> float:
    """Documented timeout policy for Community-1 end-to-end work.

    Env (optional):
      ACOUSTIC_TIMEOUT_SECONDS — if set, fixed timeout for every call
      ACOUSTIC_TIMEOUT_FLOOR_SEC — minimum (default 60)
      ACOUSTIC_TIMEOUT_BASE_SEC — intercept (default 30)
      ACOUSTIC_TIMEOUT_PER_AUDIO_SEC — seconds of budget per second of audio (default 2.5)

    Default policy: max(floor, base + per_sec * duration).
    """
    fixed = os.getenv("ACOUSTIC_TIMEOUT_SECONDS")
    if fixed is not None and str(fixed).strip() != "":
        return max(1.0, float(fixed))
    floor = float(os.getenv("ACOUSTIC_TIMEOUT_FLOOR_SEC", "60"))
    base = float(os.getenv("ACOUSTIC_TIMEOUT_BASE_SEC", "30"))
    per = float(os.getenv("ACOUSTIC_TIMEOUT_PER_AUDIO_SEC", "2.5"))
    return max(floor, base + per * max(0.0, float(audio_duration_sec)))


def _bounded_worker(
    audio_path: str,
    words: list[dict],
    asr_spans: list[tuple[float, float]],
    turn_first: bool,
    q: mp.Queue,
) -> None:
    """Module-level worker for spawn multiprocessing (must stay picklable)."""
    try:
        word_objs = [WordTiming(w["word"], w["start"], w["end"]) for w in words]
        labeled, diagnostics = build_role_segments(
            audio_path,
            word_objs,
            asr_spans,
            turn_first=turn_first,
        )
        payload = []
        for utt, role in labeled:
            payload.append(
                {
                    "start": utt.start,
                    "end": utt.end,
                    "text": utt.text,
                    "speaker_id": utt.speaker_id,
                    "ambiguous": utt.ambiguous,
                    "confidence": utt.confidence,
                    "split_from_mixed_asr": utt.split_from_mixed_asr,
                    "role": role,
                }
            )
        q.put({"ok": True, "labeled": payload, "diagnostics": diagnostics})
    except Exception as exc:  # noqa: BLE001
        q.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-4000:],
            }
        )


def run_build_role_segments_bounded(
    audio_path: str | Path,
    words: list[Any],
    asr_spans: list[tuple[float, float]],
    *,
    timeout_sec: float,
    turn_first: bool = True,
) -> tuple[list[dict], dict]:
    """Run ``build_role_segments`` in a spawn child with hard timeout.

    Returns (labeled_dicts, diagnostics).
    Raises ``TimeoutError`` if the worker is killed after timeout.
    Raises ``RuntimeError`` if the worker reports failure.
    """
    path = str(Path(audio_path))
    serial_words = [{"word": w.word, "start": float(w.start), "end": float(w.end)} for w in words]
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    proc = ctx.Process(
        target=_bounded_worker,
        args=(path, serial_words, list(asr_spans), turn_first, q),
        name="community1-build-role-segments",
    )
    global _ACTIVE_ACOUSTIC_PROC
    _ACTIVE_ACOUSTIC_PROC = proc
    proc.start()
    try:
        deadline = time.monotonic() + float(timeout_sec)
        while proc.is_alive() and time.monotonic() < deadline:
            if _CANCEL_REQUESTED:
                proc.terminate()
                proc.join(2)
                if proc.is_alive():
                    proc.kill()
                    proc.join(1)
                raise AcousticDiarizationError("Acoustic diarization cancelled.")
            proc.join(0.5)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            if proc.is_alive():
                proc.kill()
                proc.join(2)
            raise TimeoutError(
                f"Acoustic Community-1 exceeded hard timeout of {timeout_sec:.1f}s "
                f"(worker terminated; no silent retry)."
            )
        if q.empty():
            if _CANCEL_REQUESTED:
                raise AcousticDiarizationError("Acoustic diarization cancelled.")
            raise RuntimeError(
                f"Acoustic worker exited with code {proc.exitcode} and no result payload."
            )
        result = q.get()
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "Acoustic worker failed.")
        return result["labeled"], result["diagnostics"]
    finally:
        _ACTIVE_ACOUSTIC_PROC = None


def overlap_profile(
    start: float,
    end: float,
    intervals: list[tuple[float, float, str]],
) -> dict:
    """Segment-level acoustic overlap diagnostic (no speaker invention)."""

    by_speaker: dict[str, float] = {}
    for i0, i1, spk in intervals:
        o = _overlap(start, end, i0, i1)
        if o > 0:
            by_speaker[spk] = by_speaker.get(spk, 0.0) + o
    total = sum(by_speaker.values())
    dur = max(end - start, 1e-9)
    ranked = sorted(by_speaker.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        decision = "no_acoustic_coverage"
        primary = None
    elif len(ranked) == 1:
        decision = "single_speaker"
        primary = ranked[0][0]
    else:
        second = ranked[1][1]
        if second >= 0.15 or (second / dur) >= 0.15:
            decision = "mixed_speakers"
            primary = None
        else:
            decision = "single_speaker_dominant"
            primary = ranked[0][0]
    return {
        "start": round(start, 4),
        "end": round(end, 4),
        "overlap_by_speaker": {k: round(v, 4) for k, v in ranked},
        "overlap_total_sec": round(total, 4),
        "coverage_frac": round(total / dur, 4),
        "decision": decision,
        "primary_speaker_id": primary,
    }


def _labeled_to_public_segments(labeled: list[dict]) -> tuple[list[dict], int]:
    """Convert worker payloads to public segment dicts for the transcription agent."""
    out: list[dict] = []
    ambiguous_n = 0
    for item in labeled:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        role = item.get("role")
        ambiguous = bool(item.get("ambiguous")) or role is None
        conf_raw = item.get("confidence")
        conf = float(conf_raw) if conf_raw is not None else 0.2
        if ambiguous:
            ambiguous_n += 1
            speaker = "Ambiguous"
            conf = min(conf, 0.3)
        else:
            speaker = str(role)
        out.append(
            {
                "start": float(item["start"]),
                "end": float(item["end"]),
                "text": text,
                "speaker": speaker,
                "confidence": conf,
                "acoustic_speaker_id": item.get("speaker_id"),
            }
        )
    return out, ambiguous_n


def run_acoustic_diarization(
    audio_path: str | Path,
    words: list[WordTiming],
    asr_spans: list[tuple[float, float]],
    *,
    timeout_sec: float,
) -> tuple[list[dict], dict]:
    """Public acoustic entry: bounded Community-1 → Agent/Customer segments.

    Returns ``(segments, diagnostics)`` where each segment is::

        {start, end, text, speaker, confidence, acoustic_speaker_id}

    ``speaker`` is ``Agent``, ``Customer``, or ``Ambiguous``.

    Raises:
        TimeoutError: hard timeout; worker terminated; no silent retry.
        AcousticDiarizationError: inference or worker failure.
    """
    try:
        labeled, diagnostics = run_build_role_segments_bounded(
            audio_path,
            words,
            asr_spans,
            timeout_sec=timeout_sec,
            turn_first=True,
        )
    except TimeoutError:
        raise
    except Exception as exc:
        if isinstance(exc, AcousticDiarizationError):
            raise
        raise AcousticDiarizationError(str(exc)) from exc

    segments, ambiguous_n = _labeled_to_public_segments(labeled)
    diagnostics = dict(diagnostics)
    diagnostics["ambiguous_or_unmapped_utterances"] = ambiguous_n
    diagnostics["label_source"] = "acoustic"
    diagnostics["acoustic_verified"] = True
    diagnostics["acoustic_timeout_sec"] = round(float(timeout_sec), 3)
    diagnostics["labeled_payload"] = labeled  # for eval export (speaker IDs)
    diagnostics["ok"] = True
    diagnostics["fallback_activated"] = False
    return segments, diagnostics
