"""Unit tests for acoustic alignment / grouping / role mapping and transcript cleaning."""

from __future__ import annotations

from src.agents.acoustic import (
    AcousticInterval,
    AttributedWord,
    Utterance,
    WordTiming,
    align_words_to_speakers,
    collect_boundary_bleed_candidates,
    group_utterances,
    label_utterances_by_scene,
    map_roles,
    split_roleplay_scenes,
)
from src.agents.transcription import _clean_transcript_text


def test_align_majority_overlap():
    words = [
        WordTiming("hello", 0.0, 0.4),
        WordTiming("there", 0.4, 0.8),
        WordTiming("thanks", 1.0, 1.4),
    ]
    intervals = [
        AcousticInterval(0.0, 0.9, "SPEAKER_00"),
        AcousticInterval(0.95, 2.0, "SPEAKER_01"),
    ]
    out = align_words_to_speakers(words, intervals)
    assert out[0].speaker_id == "SPEAKER_00"
    assert out[1].speaker_id == "SPEAKER_00"
    assert out[2].speaker_id == "SPEAKER_01"
    assert not out[0].ambiguous


def test_align_no_overlap_is_ambiguous():
    words = [WordTiming("hi", 5.0, 5.3)]
    intervals = [AcousticInterval(0.0, 1.0, "SPEAKER_00")]
    out = align_words_to_speakers(words, intervals)
    assert out[0].speaker_id is None
    assert out[0].ambiguous
    assert out[0].reason == "no_acoustic_overlap"


def test_align_overlapping_speech_not_invented():
    words = [WordTiming("overlap", 1.0, 2.0)]
    intervals = [
        AcousticInterval(0.5, 1.8, "SPEAKER_00"),
        AcousticInterval(1.2, 2.5, "SPEAKER_01"),
    ]
    out = align_words_to_speakers(words, intervals)
    assert out[0].ambiguous
    assert out[0].reason == "overlapping_speech"
    assert out[0].speaker_id is None


def test_group_splits_different_speakers_baseline():
    words = [
        AttributedWord("yes", 0.0, 0.2, "A"),
        AttributedWord("please", 0.2, 0.5, "A"),
        AttributedWord("okay", 0.6, 0.9, "B"),
        AttributedWord("done", 0.9, 1.2, "B"),
    ]
    utts, absorptions = group_utterances(words, asr_spans=[(0.0, 1.2)], turn_first=False)
    assert absorptions == []
    assert len(utts) == 2
    assert utts[0].speaker_id == "A"
    assert utts[1].speaker_id == "B"
    assert utts[0].split_from_mixed_asr is True
    assert utts[1].split_from_mixed_asr is True


def test_group_does_not_merge_across_gap_baseline():
    words = [
        AttributedWord("one", 0.0, 0.2, "A"),
        AttributedWord("two", 2.0, 2.2, "A"),
    ]
    utts, _ = group_utterances(words, max_gap_sec=0.75, turn_first=False)
    assert len(utts) == 2


def test_baseline_ambiguous_word_hard_splits():
    words = [
        AttributedWord("agent", 0.0, 0.3, "A"),
        AttributedWord("???", 0.3, 0.5, None, ambiguous=True, reason="overlapping_speech"),
        AttributedWord("cust", 0.5, 0.8, "B"),
    ]
    utts, _ = group_utterances(words, turn_first=False)
    assert len(utts) == 3
    assert utts[0].speaker_id == "A"
    assert utts[1].ambiguous and utts[1].speaker_id is None
    assert utts[2].speaker_id == "B"


def test_turn_first_neighbor_continuity_across_gap():
    """In-turn island with no acoustic hit: both clear neighbors agree → nearest turn."""
    intervals = [
        AcousticInterval(0.0, 0.4, "SPEAKER_00"),
        AcousticInterval(0.55, 1.0, "SPEAKER_00"),
    ]
    words = [
        AttributedWord("thank", 0.0, 0.2, "SPEAKER_00"),
        AttributedWord("you", 0.2, 0.35, "SPEAKER_00"),
        AttributedWord("we", 0.45, 0.5, None, True, "no_acoustic_overlap"),
        AttributedWord("really", 0.6, 0.8, "SPEAKER_00"),
    ]
    utts, absorptions = group_utterances(words, intervals=intervals, turn_first=True)
    assert len(absorptions) == 1
    assert absorptions[0]["absorption"] == "neighbor_continuity"
    assert absorptions[0]["absorbed_into_speaker_id"] == "SPEAKER_00"
    assert any("we" in u.text and u.speaker_id == "SPEAKER_00" for u in utts)


def test_turn_first_absorbs_isolated_ambiguous_inside_turn():
    intervals = [AcousticInterval(0.0, 1.0, "SPEAKER_00")]
    words = [
        AttributedWord("thank", 0.0, 0.2, "SPEAKER_00"),
        AttributedWord("you", 0.2, 0.4, "SPEAKER_00"),
        AttributedWord("we", 0.45, 0.45, None, True, "no_acoustic_overlap"),
        AttributedWord("really", 0.5, 0.7, "SPEAKER_00"),
    ]
    utts, absorptions = group_utterances(words, intervals=intervals, turn_first=True)
    assert len(utts) == 1
    assert utts[0].speaker_id == "SPEAKER_00"
    assert utts[0].ambiguous is False
    assert "we" in utts[0].text
    assert len(absorptions) == 1
    assert absorptions[0]["original_reason"] == "no_acoustic_overlap"
    assert absorptions[0]["absorbed_into_speaker_id"] == "SPEAKER_00"
    # Word-level uncertainty preserved on the AttributedWord inside the utterance
    absorbed = [w for w in utts[0].words if w.word == "we"][0]
    assert absorbed.ambiguous is True
    assert absorbed.reason == "no_acoustic_overlap"


def test_turn_first_preserves_clear_align_despite_tiny_other_turn_hit():
    """Sample 03 'Yeah,' regression: unambiguous SPEAKER_00 must not become Ambiguous
    just because the Whisper span nicks another turn by ~15ms."""
    intervals = [
        AcousticInterval(37.95, 40.67, "SPEAKER_00"),
        AcousticInterval(41.64, 42.00, "SPEAKER_01"),
    ]
    words = [
        AttributedWord("Yeah,", 40.46, 41.66, "SPEAKER_00", False, "overlap_majority"),
    ]
    utts, absorptions = group_utterances(words, intervals=intervals, turn_first=True)
    assert absorptions == []
    assert len(utts) == 1
    assert utts[0].speaker_id == "SPEAKER_00"
    assert utts[0].ambiguous is False
    assert utts[0].text == "Yeah,"
    assert not any(u.ambiguous or u.speaker_id is None for u in utts)


def test_turn_first_asr_span_continuation_at_nonoverlapping_boundary():
    """Bleed across adjacent non-overlapping turns: unanimous clear ASR peers win."""
    intervals = [
        AcousticInterval(0.0, 0.5, "SPEAKER_00"),
        AcousticInterval(0.6, 1.2, "SPEAKER_01"),
    ]
    words = [
        AttributedWord("altima", 0.0, 0.4, "SPEAKER_00"),
        AttributedWord("Oh", 0.3, 0.9, None, True, "overlapping_speech"),
        AttributedWord("nice", 0.7, 0.9, "SPEAKER_01"),
        AttributedWord("car", 0.9, 1.1, "SPEAKER_01"),
    ]
    # "Oh nice car" share one ASR span; clear peers are unanimously SPEAKER_01.
    utts, absorptions = group_utterances(
        words,
        intervals=intervals,
        asr_spans=[(0.0, 0.4), (0.3, 1.1)],
        turn_first=True,
    )
    assert len(absorptions) == 1
    assert absorptions[0]["absorption"] == "asr_span_continuation"
    assert absorptions[0]["absorbed_into_speaker_id"] == "SPEAKER_01"
    absorbed = next(u for u in utts if "Oh" in u.text and u.speaker_id == "SPEAKER_01")
    oh = next(w for w in absorbed.words if w.word == "Oh")
    assert oh.ambiguous is True
    assert oh.reason == "overlapping_speech"
    assert oh.start == 0.3 and oh.end == 0.9


def test_turn_first_keeps_genuine_overlap_unresolved():
    intervals = [
        AcousticInterval(0.0, 1.0, "SPEAKER_00"),
        AcousticInterval(0.4, 1.2, "SPEAKER_01"),  # true overlap with SPEAKER_00
    ]
    words = [
        AttributedWord("left", 0.0, 0.3, "SPEAKER_00"),
        AttributedWord("mix", 0.5, 0.9, None, True, "overlapping_speech"),
        AttributedWord("right", 1.0, 1.15, "SPEAKER_01"),
    ]
    utts, absorptions = group_utterances(
        words, intervals=intervals, asr_spans=[(0.5, 0.9)], turn_first=True
    )
    assert absorptions == []
    amb = [u for u in utts if u.ambiguous]
    assert len(amb) == 1
    assert amb[0].text == "mix"


def test_turn_first_does_not_absorb_multi_turn_hits():
    """Word overlapping two different-speaker turns stays unresolved without peers."""
    intervals = [
        AcousticInterval(0.0, 1.0, "SPEAKER_00"),
        AcousticInterval(1.2, 2.0, "SPEAKER_01"),
    ]
    words = [
        AttributedWord("bleed", 0.8, 1.5, None, True, "no_acoustic_overlap"),
    ]
    utts, absorptions = group_utterances(words, intervals=intervals, turn_first=True)
    assert absorptions == []
    assert len(utts) == 1
    assert utts[0].ambiguous is True


def test_turn_first_align_id_neighbor_continuation():
    """boundary_collar ID + agreeing clear neighbor → absorb despite multi-turn nick."""
    intervals = [
        AcousticInterval(0.0, 1.0, "SPEAKER_01"),
        AcousticInterval(1.05, 1.08, "SPEAKER_01"),
        AcousticInterval(1.08, 2.0, "SPEAKER_00"),
    ]
    words = [
        AttributedWord("Oh,", 1.0, 1.15, "SPEAKER_00", True, "boundary_collar"),
        AttributedWord("OK.", 1.2, 1.4, "SPEAKER_00", False, "overlap_majority"),
    ]
    utts, absorptions = group_utterances(words, intervals=intervals, turn_first=True)
    assert len(absorptions) == 1
    assert absorptions[0]["absorption"] == "align_id_neighbor_continuation"
    assert absorptions[0]["absorbed_into_speaker_id"] == "SPEAKER_00"
    assert all(not u.ambiguous for u in utts)


def test_boundary_bleed_flagged_not_reassigned():
    words = [WordTiming("Oh", 36.58, 37.60)]
    intervals = [
        AcousticInterval(33.63, 36.95, "SPEAKER_00"),
        AcousticInterval(37.44, 38.32, "SPEAKER_01"),
    ]
    attributed = align_words_to_speakers(words, intervals)
    assert attributed[0].reason == "overlapping_speech"
    flags = collect_boundary_bleed_candidates(words, intervals, attributed)
    assert len(flags) == 1
    assert flags[0]["auto_reassigned"] is False
    assert flags[0]["majority_overlap_speaker"] == "SPEAKER_00"
    assert flags[0]["hypothetical_clamp_speaker"] == "SPEAKER_01"
    assert flags[0]["clamp_vs_majority_disagree"] is True


def test_true_acoustic_overlap_not_bleed_candidate():
    words = [WordTiming("overlap", 1.0, 2.0)]
    intervals = [
        AcousticInterval(0.5, 1.8, "SPEAKER_00"),
        AcousticInterval(1.2, 2.5, "SPEAKER_01"),
    ]
    attributed = align_words_to_speakers(words, intervals)
    flags = collect_boundary_bleed_candidates(words, intervals, attributed)
    assert flags == []


def test_role_mapping_uses_greeting_not_speaker_index():
    utts = [
        Utterance(10.0, 12.0, "Thank you for calling Nissan.", "SPEAKER_01", False, 0.9),
        Utterance(12.5, 14.0, "Hi I need help.", "SPEAKER_00", False, 0.9),
    ]
    mapping = map_roles(utts)
    assert mapping.mapping["SPEAKER_01"] == "Agent"
    assert mapping.mapping["SPEAKER_00"] == "Customer"
    assert mapping.method == "opening_greeting_cues"


def test_role_mapping_scans_past_window_when_empty():
    """sample_07: greeting at 45.2s must beat the 0.18s count-in."""
    utts = [
        Utterance(0.18, 1.88, "One, two, three,", "SPEAKER_01", False, 0.9),
        Utterance(
            45.20,
            49.46,
            "Hi, thank you for calling Hotel California. How may I help you?",
            "SPEAKER_00",
            False,
            0.9,
        ),
    ]
    mapping = map_roles(utts)
    assert mapping.mapping["SPEAKER_00"] == "Agent"
    assert mapping.mapping["SPEAKER_01"] == "Customer"
    assert mapping.method == "opening_greeting_cues"


def test_role_mapping_keeps_in_window_cues_if_later_speaker_greets():
    """sample_09-style second scenario must not rewrite the first-call mapping."""
    utts = [
        Utterance(
            10.0,
            12.0,
            "Thank you for calling support. How may I help you?",
            "SPEAKER_00",
            False,
            0.9,
        ),
        Utterance(20.0, 21.0, "My package is late.", "SPEAKER_01", False, 0.9),
        Utterance(
            159.0,
            162.0,
            "Thank you for calling support. How may I help you?",
            "SPEAKER_01",
            False,
            0.9,
        ),
        Utterance(164.0, 166.0, "I've been overcharged.", "SPEAKER_00", False, 0.9),
    ]
    mapping = map_roles(utts)
    assert mapping.mapping["SPEAKER_00"] == "Agent"
    assert mapping.mapping["SPEAKER_01"] == "Customer"


def test_scene_labeling_remaps_after_customer_opening_cue():
    """sample_09 call 2: Patrick greeting on the first-call Customer ID."""
    utts = [
        Utterance(
            10.0,
            12.0,
            "Thank you for calling support. How may I help you?",
            "SPEAKER_00",
            False,
            0.9,
        ),
        Utterance(20.0, 21.0, "My package is late.", "SPEAKER_01", False, 0.9),
        Utterance(143.0, 144.0, "Goodbye.", "SPEAKER_00", False, 0.9),
        Utterance(
            159.0,
            162.0,
            "Thank you for calling support. How may I help you?",
            "SPEAKER_01",
            False,
            0.9,
        ),
        Utterance(164.0, 166.0, "I've been overcharged.", "SPEAKER_00", False, 0.9),
    ]
    labeled, maps = label_utterances_by_scene(utts)
    assert len(maps) == 2
    roles = {round(u.start, 1): role for u, role in labeled}
    assert roles[10.0] == "Agent"
    assert roles[20.0] == "Customer"
    assert roles[159.0] == "Agent"
    assert roles[164.0] == "Customer"


def test_scene_split_keeps_greeting_cluster_in_one_scene():
    utts = [
        Utterance(
            10.0,
            12.0,
            "Thank you for calling. How may I help you?",
            "SPEAKER_00",
            False,
            0.9,
        ),
        Utterance(20.0, 21.0, "My package is late.", "SPEAKER_01", False, 0.9),
        Utterance(157.8, 158.4, "Good afternoon.", "SPEAKER_01", False, 0.9),
        Utterance(159.0, 161.8, "Thank you for calling support.", "SPEAKER_01", False, 0.9),
        Utterance(162.5, 163.5, "How may I assist you today?", "SPEAKER_01", False, 0.9),
        Utterance(166.8, 169.0, "I've been overcharged.", "SPEAKER_00", False, 0.9),
    ]
    labeled, maps = label_utterances_by_scene(utts)
    assert len(maps) == 2
    roles = {round(u.start, 1): role for u, role in labeled}
    assert roles[157.8] == "Agent"
    assert roles[159.0] == "Agent"
    assert roles[166.8] == "Customer"


def test_scene_split_peels_same_speaker_greeting_tail():
    utts = [
        Utterance(
            10.0,
            12.0,
            "Thank you for calling. How may I help you?",
            "SPEAKER_00",
            False,
            0.9,
        ),
        Utterance(20.0, 21.0, "Hi I have a question.", "SPEAKER_01", False, 0.9),
        Utterance(210.8, 212.7, "you for calling vital care", "SPEAKER_01", False, 0.9),
        Utterance(213.1, 213.9, "My name is Carson.", "SPEAKER_01", False, 0.9),
        Utterance(214.4, 215.4, "How may I assist you today?", "SPEAKER_01", False, 0.9),
    ]
    scenes = split_roleplay_scenes(utts, map_roles(utts))
    assert len(scenes) == 2
    assert [round(u.start, 1) for u in scenes[1]] == [210.8, 213.1, 214.4]


def test_youve_reached_on_customer_does_not_start_a_scene():
    utts = [
        Utterance(10.0, 12.0, "Thank you for calling prepaid.", "SPEAKER_01", False, 0.9),
        Utterance(20.0, 21.0, "Okay.", "SPEAKER_00", False, 0.9),
        Utterance(
            305.0,
            307.0,
            "once you've reached your third month with us",
            "SPEAKER_00",
            False,
            0.9,
        ),
    ]
    labeled, maps = label_utterances_by_scene(utts)
    assert len(maps) == 1
    assert labeled[0][1] == "Agent"
    assert labeled[2][1] == "Customer"


def test_collapsed_roleplay_scene_requires_one_id_and_greeting():
    from src.agents.acoustic import _collapsed_roleplay_scene

    greeting = [
        Utterance(210.0, 211.0, "How may I assist you today?", "SPEAKER_01", False, 0.9),
        Utterance(216.0, 218.0, "Hi I have questions.", "SPEAKER_01", False, 0.9),
        Utterance(223.0, 225.0, "Of course.", "SPEAKER_01", False, 0.9),
        Utterance(229.0, 232.0, "Sure my name is Monique.", "SPEAKER_01", False, 0.9),
    ]
    assert _collapsed_roleplay_scene(greeting) is True
    two_ids = list(greeting)
    two_ids[1] = Utterance(216.0, 218.0, "Hi I have questions.", "SPEAKER_00", False, 0.9)
    assert _collapsed_roleplay_scene(two_ids) is False


def test_clean_transcript_text_removes_artifacts():
    assert _clean_transcript_text("hello [BLANK_AUDIO] there") == "hello there"
    assert _clean_transcript_text("hi thanks for watching.") == "hi"
    assert _clean_transcript_text("hold [MUSIC] please") == "hold please"
    assert _clean_transcript_text("hold music please") == "hold music please"
    assert _clean_transcript_text("hello....there") == "hello...there"
    assert _clean_transcript_text("thank you thank you thank you") == "thank you"


def test_avg_logprob_zero_is_preserved():
    """Regression: numeric 0.0 must not be replaced via falsey `or`."""
    from src.agents.transcription import _sentence_units_from_whisper

    class _W:
        word = "hi"
        start = 0.0
        end = 0.2

    class _Seg:
        start = 0.0
        end = 0.5
        text = "hi"
        words = [_W()]
        avg_logprob = 0.0
        no_speech_prob = 0.0

    units = _sentence_units_from_whisper([_Seg()])
    assert units
    assert units[0].avg_logprob == 0.0
    assert units[0].no_speech_prob == 0.0


def test_acoustic_labeled_confidence_zero_preserved():
    from src.agents.acoustic import _labeled_to_public_segments

    segs, amb = _labeled_to_public_segments(
        [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "hello",
                "speaker_id": "SPEAKER_00",
                "ambiguous": False,
                "confidence": 0.0,
                "role": "Agent",
            }
        ]
    )
    assert amb == 0
    assert segs[0]["confidence"] == 0.0


def test_speaker_diarizer_importable_from_transcription():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    assert d.previous_speaker is None
    assert d.last_confident_speaker is None


class _Seg:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


def test_speaker_diarizer_exclusive_patterns_set_confident_state():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    assert d.assign_speaker(_Seg(0.0, 1.0, "Thank you for calling support.")) == "Agent"
    assert d.last_confident_speaker == "Agent"
    assert d.assign_speaker(_Seg(1.5, 3.0, "I am calling about my order.")) == "Customer"
    assert d.last_confident_speaker == "Customer"


def test_speaker_diarizer_fallback_uses_pattern_anchor_not_weak_guess():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    # Opening default is weak — next non-cue segment must not cascade from it.
    assert d.assign_speaker(_Seg(0.0, 1.0, "Hello there.")) == "Agent"
    assert d.last_confident_speaker is None
    assert d.assign_speaker(_Seg(1.1, 2.0, "Something unrelated.")) == "Ambiguous"

    # Pattern establishes anchor; FALLBACK continues from that after a one-shot switch.
    assert d.assign_speaker(_Seg(2.0, 3.0, "How may I help you today?")) == "Agent"
    assert d.last_confident_speaker == "Agent"
    assert d.assign_speaker(_Seg(3.5, 4.5, "Okay thanks.")) == "Customer"  # QUESTION_SWITCH
    assert d.last_confident_speaker == "Agent"
    assert d.assign_speaker(_Seg(4.6, 5.5, "We can look into that next.")) == "Agent"


def test_speaker_diarizer_question_switch_still_fires():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    assert d.assign_speaker(_Seg(0.0, 1.0, "I'd be happy to help.")) == "Agent"
    assert d.assign_speaker(_Seg(1.0, 2.0, "What is your account number?")) == "Agent"
    assert d.assign_speaker(_Seg(2.2, 3.0, "Sure thing.")) == "Customer"


def test_two_pass_dialogue_act_question_then_answer():
    from src.agents.transcription import _dialogue_act_labels, _SentenceUnit

    units = [
        _SentenceUnit(0.0, 1.0, "How may I help you today?", "Agent", 6, "question", -0.2, 0.1),
        _SentenceUnit(1.2, 2.5, "I need help with billing.", None, 5, "statement", -0.2, 0.1),
        _SentenceUnit(2.6, 3.5, "I'd be happy to help.", "Agent", 5, "statement", -0.2, 0.1),
    ]
    # One-shot flip on the answer, then pattern pins Agent again.
    assert _dialogue_act_labels(units) == ["Agent", "Customer", "Agent"]


def test_two_pass_dialogue_act_fallback_to_pattern_anchor():
    from src.agents.transcription import _dialogue_act_labels, _SentenceUnit

    units = [
        _SentenceUnit(0.0, 1.0, "I'd be happy to help.", "Agent", 5, "statement", -0.2, 0.1),
        _SentenceUnit(
            1.1,
            2.0,
            "The price of the update is ninety nine dollars today.",
            None,
            11,
            "statement",
            -0.2,
            0.1,
        ),
        _SentenceUnit(2.1, 2.4, "Okay.", None, 1, "ack", -0.2, 0.1),
        _SentenceUnit(2.5, 3.5, "Shipping is included.", None, 3, "statement", -0.2, 0.1),
    ]
    # long→ack flips once; next statement falls back to pattern anchor Agent.
    assert _dialogue_act_labels(units) == ["Agent", "Agent", "Customer", "Agent"]


def test_two_pass_short_reply_then_followup_question_stays_same_speaker():
    """sample_01: 'I did.' then 'Do you need the customer number?' — both Customer."""
    from src.agents.transcription import _dialogue_act_labels, _SentenceUnit

    units = [
        _SentenceUnit(
            20.62,
            23.82,
            "Did you receive a mailer from us?",
            "Agent",
            7,
            "question",
            -0.2,
            0.1,
        ),
        _SentenceUnit(24.00, 24.38, "I did.", None, 2, "statement", -0.2, 0.1),
        _SentenceUnit(
            24.80,
            26.14,
            "Do you need the customer number?",
            None,
            6,
            "question",
            -0.2,
            0.1,
        ),
        _SentenceUnit(26.54, 26.90, "Yes please.", None, 2, "statement", -0.2, 0.1),
    ]
    assert _dialogue_act_labels(units) == [
        "Agent",
        "Customer",
        "Customer",
        "Agent",
    ]


def test_cleaner_preserves_ordinary_speech_about_nonspeech_labels():
    text = "The music subscription stopped working during the silence."
    assert _clean_transcript_text(text) == text
    assert _clean_transcript_text("music") == ""
    assert _clean_transcript_text("[applause] Hello.") == "Hello."


def test_consecutive_questions_switch_from_previous_speaker():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    assert d.assign_speaker(_Seg(0, 1, "How may I help you?")) == "Agent"
    assert d.assign_speaker(_Seg(1, 2, "Can we discuss this?")) == "Customer"
    assert d.assign_speaker(_Seg(2, 3, "Certainly.")) == "Agent"


def test_acoustic_word_cleaning_preserves_spoken_music():
    from types import SimpleNamespace as S

    from src.agents.transcription import _words_and_spans_from_whisper

    words, _ = _words_and_spans_from_whisper(
        [
            S(
                text="My music stopped",
                start=0,
                end=3,
                words=[
                    S(word=w, start=i, end=i + 1) for i, w in enumerate(["My", "music", "stopped"])
                ],
            ),
            S(
                text="[MUSIC]",
                start=3,
                end=4,
                words=[S(word="[MUSIC]", start=3, end=4)],
            ),
        ]
    )
    assert [w.word for w in words] == ["My", "music", "stopped"]


def test_speaker_priority_gap_boundary_and_affirmation():
    from src.agents.transcription import SpeakerDiarizer

    d = SpeakerDiarizer()
    assert d.assign_speaker(_Seg(0, 1, "I am calling about my order.")) == "Customer"
    # A content cue outranks both the long gap and question cue.
    assert d.assign_speaker(_Seg(4, 5, "I am calling about my bill?")) == "Customer"
    assert d.assign_speaker(_Seg(8, 9, "I am calling about my order.")) == "Customer"
    assert d.assign_speaker(_Seg(10.2, 11, "Nothing else.")) == "Customer"
    assert d.assign_speaker(_Seg(12.3, 13, "Nothing else.")) == "Agent"
    d = SpeakerDiarizer()
    d.assign_speaker(
        _Seg(0, 1, "Let me check your account and see why the payment has not arrived.")
    )
    assert d.assign_speaker(_Seg(1, 2, "Yes.")) == "Customer"
