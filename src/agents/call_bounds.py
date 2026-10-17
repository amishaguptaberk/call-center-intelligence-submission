"""Detect real call window; UI shows only in-call content.

Wrapper audio (briefing / YouTube outro) is still transcribed so we can find
greeting/outro cues, but the debug UI clips playback and hides those rows.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.graph.state import TranscriptionSegment

_CALL_START_CUES = [
    re.compile(r"\bthank you for calling\b", re.IGNORECASE),
    re.compile(r"\bthanks for calling\b", re.IGNORECASE),
    re.compile(r"\bhow (?:may|can) I (?:help|assist) you\b", re.IGNORECASE),
    re.compile(r"\byou(?:'ve| have) reached\b", re.IGNORECASE),
]

_CALL_META_CUES = [
    re.compile(r"\bthumbs up\b", re.IGNORECASE),
    re.compile(r"\broleplay\b", re.IGNORECASE),
    re.compile(r"\bclick the link\b", re.IGNORECASE),
    re.compile(r"\bthat'?s all for today\b", re.IGNORECASE),
    re.compile(r"\bcall flow step by step\b", re.IGNORECASE),
    re.compile(r"\bproduct knowledge of this mock\b", re.IGNORECASE),
    re.compile(r"\benjoyed this video\b", re.IGNORECASE),
    re.compile(r"\bwatch our other\b", re.IGNORECASE),
    re.compile(r"\bdetailed explanation as to why\b", re.IGNORECASE),
    re.compile(r"\bfamiliarize all of these\b", re.IGNORECASE),
]

MARKER_SPEAKERS = frozenset({"Hold", "CallStart", "CallEnd"})


@dataclass(frozen=True)
class CallBounds:
    start_sec: float | None
    end_sec: float | None
    start_index: int | None
    end_index: int | None
    trimmed: bool
    prelude_sec: float = 0.0
    outro_sec: float = 0.0
    prelude_rows: int = 0
    outro_rows: int = 0
    prelude_preview: str = ""
    outro_preview: str = ""
    call_start_text: str = ""


def _is_speech(seg: TranscriptionSegment) -> bool:
    return seg.speaker not in MARKER_SPEAKERS


def _matches(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(text or "") for p in patterns)


def _fmt_clock(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"


def _preview(text: str, limit: int = 72) -> str:
    one = " ".join((text or "").split())
    if len(one) <= limit:
        return one
    return one[: limit - 1] + "…"


def find_call_bounds(segments: list[TranscriptionSegment]) -> CallBounds:
    speech = [s for s in segments if _is_speech(s)]
    if not speech:
        return CallBounds(None, None, None, None, False)

    start_i = next(
        (i for i, s in enumerate(speech) if _matches(s.text, _CALL_START_CUES)),
        None,
    )
    if start_i is None:
        return CallBounds(
            speech[0].start_time,
            speech[-1].end_time,
            0,
            len(speech) - 1,
            False,
            call_start_text=_preview(speech[0].text),
        )

    end_i = len(speech) - 1
    for i in range(start_i + 1, len(speech)):
        if _matches(speech[i].text, _CALL_META_CUES):
            end_i = i - 1
            break
    end_i = max(end_i, start_i)

    trimmed = start_i > 0 or end_i < len(speech) - 1
    prelude = speech[:start_i]
    outro = speech[end_i + 1 :]
    prelude_sec = round(speech[start_i].start_time - speech[0].start_time, 3) if prelude else 0.0
    outro_sec = round(speech[-1].end_time - speech[end_i].end_time, 3) if outro else 0.0
    return CallBounds(
        speech[start_i].start_time,
        speech[end_i].end_time,
        start_i,
        end_i,
        trimmed,
        prelude_sec=prelude_sec,
        outro_sec=outro_sec,
        prelude_rows=len(prelude),
        outro_rows=len(outro),
        prelude_preview=_preview(prelude[0].text) if prelude else "",
        outro_preview=_preview(outro[0].text) if outro else "",
        call_start_text=_preview(speech[start_i].text),
    )


def in_call_segments(
    segments: list[TranscriptionSegment],
    *,
    relative_times: bool = True,
) -> tuple[list[TranscriptionSegment], CallBounds]:
    """Keep only Agent/Customer (etc.) rows inside the call window.

    Timestamps are shifted to 0 at call start so they match clipped playback.
    """
    bounds = find_call_bounds(segments)
    speech = [s for s in segments if _is_speech(s)]
    if bounds.start_index is None or bounds.end_index is None:
        return list(speech), bounds

    slice_ = speech[bounds.start_index : bounds.end_index + 1]
    if not relative_times or bounds.start_sec is None:
        return slice_, bounds

    origin = bounds.start_sec
    shifted = [
        s.model_copy(
            update={
                "start_time": round(max(0.0, s.start_time - origin), 3),
                "end_time": round(max(0.0, s.end_time - origin), 3),
            }
        )
        for s in slice_
    ]
    return shifted, bounds


def call_bounds_summary(bounds: CallBounds) -> str:
    """One-line status chip."""
    if bounds.start_sec is None or bounds.end_sec is None:
        return "Call bounds: whole file (no greeting cue)"
    dur = bounds.end_sec - bounds.start_sec
    base = (
        f"Call starts @ file {_fmt_clock(bounds.start_sec)} "
        f"→ ends @ {_fmt_clock(bounds.end_sec)} ({dur:.1f}s in-call)"
    )
    if not bounds.trimmed:
        return base
    bits = []
    if bounds.prelude_rows:
        bits.append(f"hid prelude {bounds.prelude_sec:.1f}s/{bounds.prelude_rows} rows")
    if bounds.outro_rows:
        bits.append(f"hid outro {bounds.outro_sec:.1f}s/{bounds.outro_rows} rows")
    return f"{base} — {'; '.join(bits)}"


def call_bounds_notice(bounds: CallBounds) -> str:
    """Multi-line notice for the transcript panel when wrapper may be hidden."""
    if bounds.start_sec is None or bounds.end_sec is None:
        return "Call bounds: whole file (no opening greeting found)."
    lines = [
        (
            f"In-call window (file clock): {_fmt_clock(bounds.start_sec)}"
            f" – {_fmt_clock(bounds.end_sec)}"
        ),
        "Playback/table timestamps restart at 00:00.00 for that window.",
    ]
    if bounds.call_start_text:
        lines.append(f"Call starts on: “{bounds.call_start_text}”")
    if not bounds.trimmed:
        lines.append("No prelude/outro detected — showing full transcript.")
        return "\n".join(lines)
    if bounds.prelude_rows:
        lines.append(
            f"Left out prelude: {_fmt_clock(0)}–{_fmt_clock(bounds.start_sec)} "
            f"({bounds.prelude_sec:.1f}s, {bounds.prelude_rows} rows)"
            + (f" starting “{bounds.prelude_preview}”" if bounds.prelude_preview else "")
        )
    if bounds.outro_rows and bounds.end_sec is not None:
        outro_end = bounds.end_sec + bounds.outro_sec
        lines.append(
            f"Left out outro: {_fmt_clock(bounds.end_sec)}–{_fmt_clock(outro_end)} "
            f"({bounds.outro_sec:.1f}s, {bounds.outro_rows} rows)"
            + (f" starting “{bounds.outro_preview}”" if bounds.outro_preview else "")
        )
    return "\n".join(lines)


def write_call_audio_clip(
    audio_path: str | Path,
    start_sec: float,
    end_sec: float,
    *,
    dest_dir: Path | None = None,
) -> Path:
    """Write a mono WAV of [start_sec, end_sec] for UI playback."""
    import librosa
    import soundfile as sf

    src = Path(audio_path)
    duration = max(float(end_sec) - float(start_sec), 0.05)
    samples, sr = librosa.load(
        str(src),
        sr=None,
        mono=True,
        offset=max(0.0, float(start_sec)),
        duration=duration,
    )
    out_dir = dest_dir or Path(tempfile.gettempdir()) / "call_center_clips"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{src.stem}_call_{int(start_sec)}-{int(end_sec)}.wav"
    sf.write(str(dest), samples, int(sr))
    return dest
