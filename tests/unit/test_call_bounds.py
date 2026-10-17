"""Call-window detection for in-call-only UI."""

from __future__ import annotations

from src.agents.call_bounds import find_call_bounds, in_call_segments
from src.graph.state import TranscriptionSegment


def _seg(start: float, end: float, speaker: str, text: str) -> TranscriptionSegment:
    return TranscriptionSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker=speaker,
        confidence=0.85,
    )


def test_in_call_segments_drops_prelude_and_outro():
    segs = [
        _seg(0.0, 2.0, "Agent", "Here is the product knowledge of this mock call."),
        _seg(3.0, 4.0, "Agent", "And now let's begin."),
        _seg(5.0, 8.0, "Agent", "Thank you for calling Power Up. How may I help you?"),
        _seg(9.0, 10.0, "Customer", "Hi I have a billing question."),
        _seg(11.0, 12.0, "Agent", "Happy to help."),
        _seg(13.0, 15.0, "Agent", "If you enjoyed this video give us a thumbs up."),
    ]
    in_call, bounds = in_call_segments(segs)
    assert bounds.trimmed is True
    assert bounds.start_sec == 5.0
    assert bounds.prelude_rows == 2
    assert bounds.outro_rows == 1
    assert "product knowledge" in bounds.prelude_preview
    assert "thumbs up" in bounds.outro_preview
    assert "Thank you for calling" in bounds.call_start_text
    from src.agents.call_bounds import call_bounds_notice

    notice = call_bounds_notice(bounds)
    assert "Call starts on:" in notice
    assert "Left out prelude:" in notice
    assert "Left out outro:" in notice
    texts = [s.text for s in in_call]
    assert texts[0].startswith("Thank you for calling")
    assert "product knowledge" not in " ".join(texts)
    assert "thumbs up" not in " ".join(texts)
    assert in_call[0].start_time == 0.0
    assert abs(in_call[1].start_time - 4.0) < 0.01


def test_find_call_bounds_whole_file_without_greeting():
    segs = [
        _seg(0.0, 1.0, "Agent", "Hello there."),
        _seg(2.0, 3.0, "Customer", "Hi."),
    ]
    bounds = find_call_bounds(segs)
    assert bounds.trimmed is False
    assert bounds.start_index == 0
    assert bounds.end_index == 1
