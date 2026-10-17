"""Post-call wait / hold gaps derived from labeled speech segments.

Does not classify hold-music vs other-line; silence ≥ threshold is enough for QA.
Hold rows are for human transcripts — keep them out of Agent/Customer scoring.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from src.graph.state import TranscriptionSegment

# ~10s holds clear this; normal 3–5s pauses do not.
DEFAULT_HOLD_MIN_SEC = 8.0
_NON_SPEECH = frozenset({"Hold", "CallStart", "CallEnd"})


@dataclass(frozen=True)
class WaitEvent:
    start: float
    end: float
    duration_sec: float
    after_speaker: str
    before_speaker: str


def compute_wait_events(
    segments: list[TranscriptionSegment],
    *,
    min_sec: float = DEFAULT_HOLD_MIN_SEC,
) -> list[WaitEvent]:
    """Silence gaps between consecutive speech segments (skips marker rows)."""
    speech = [s for s in segments if s.speaker not in _NON_SPEECH]
    if len(speech) < 2:
        return []
    ordered = sorted(speech, key=lambda s: (s.start_time, s.end_time))
    events: list[WaitEvent] = []
    for prev, cur in itertools.pairwise(ordered):
        gap = cur.start_time - prev.end_time
        if gap >= min_sec:
            events.append(
                WaitEvent(
                    start=prev.end_time,
                    end=cur.start_time,
                    duration_sec=round(gap, 3),
                    after_speaker=prev.speaker,
                    before_speaker=cur.speaker,
                )
            )
    return events


def hold_segment(event: WaitEvent) -> TranscriptionSegment:
    return TranscriptionSegment(
        start_time=event.start,
        end_time=event.end,
        text=f"[hold {event.duration_sec:.1f}s]",
        speaker="Hold",
        confidence=1.0,
    )


def with_hold_markers(
    segments: list[TranscriptionSegment],
    *,
    min_sec: float = DEFAULT_HOLD_MIN_SEC,
) -> list[TranscriptionSegment]:
    """Speech/marker segments plus inline Hold rows for transcript display."""
    events = compute_wait_events(segments, min_sec=min_sec)
    if not events:
        return list(segments)
    holds = [hold_segment(e) for e in events]
    # Keep existing non-Hold rows; drop stale Hold rows then re-insert.
    base = [s for s in segments if s.speaker != "Hold"]
    merged = base + holds
    merged.sort(key=lambda s: (s.start_time, s.end_time, 0 if s.speaker != "Hold" else 1))
    return merged


def wait_summary_line(events: list[WaitEvent]) -> str:
    if not events:
        return "Wait: none (≥8s gaps)"
    total = sum(e.duration_sec for e in events)
    n = len(events)
    return f"Wait: {total:.1f}s total ({n} hold{'s' if n != 1 else ''})"


def for_display(segments: list[TranscriptionSegment]):
    """In-call rows only (relative times) + hold gaps. Returns (segments, call_bounds)."""
    from src.agents.call_bounds import in_call_segments

    in_call, bounds = in_call_segments(segments, relative_times=True)
    return with_hold_markers(in_call), bounds
