"""Wait / hold gap markers for post-call transcripts."""

from __future__ import annotations

from src.agents.wait_events import (
    compute_wait_events,
    wait_summary_line,
    with_hold_markers,
)
from src.graph.state import TranscriptionSegment


def _seg(start: float, end: float, speaker: str, text: str) -> TranscriptionSegment:
    return TranscriptionSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker=speaker,
        confidence=0.9,
    )


def test_compute_wait_events_ignores_short_gaps():
    segs = [
        _seg(0.0, 1.0, "Agent", "Hello"),
        _seg(4.0, 5.0, "Customer", "Hi"),  # 3s gap
    ]
    assert compute_wait_events(segs, min_sec=8.0) == []


def test_compute_wait_events_and_transcript_markers():
    segs = [
        _seg(0.0, 1.0, "Agent", "One moment"),
        _seg(11.5, 12.0, "Agent", "Thanks for holding"),  # 10.5s
        _seg(12.5, 13.0, "Customer", "Okay"),
    ]
    events = compute_wait_events(segs, min_sec=8.0)
    assert len(events) == 1
    assert events[0].duration_sec == 10.5
    assert events[0].after_speaker == "Agent"

    marked = with_hold_markers(segs, min_sec=8.0)
    assert [s.speaker for s in marked] == ["Agent", "Hold", "Agent", "Customer"]
    assert marked[1].text == "[hold 10.5s]"
    assert "10.5s total" in wait_summary_line(events)
