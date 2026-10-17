"""Milestone 3 transcription agent: Whisper + speaker labeling.

Orchestrates ASR and diarization. Acoustic Community-1 details live in
``src.agents.acoustic`` behind ``run_acoustic_diarization``.

Backends (``DIARIZATION_BACKEND``):
  heuristic — text SpeakerDiarizer / sentence dialogue-act baseline
  acoustic  — Community-1 only (raises on failure)
  hybrid    — Community-1 with hard timeout; heuristic fallback on failure
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.agents.acoustic import (
    AcousticDiarizationError,
    WordTiming,
    acoustic_timeout_sec,
    run_acoustic_diarization,
)
from src.database.connection import init_db, session_scope
from src.database.models import TranscriptionCache
from src.graph.state import IntakeResult, TranscriptionResult, TranscriptionSegment
from src.utils.config import load_config

config = None

_model = None
_model_size = None
_LAST_DIAGNOSTICS: dict | None = None
_LAST_WHISPER_INIT_SEC: float | None = None

_AGENT_PATTERNS = [
    re.compile(r"\b(?:thank you for calling|thanks for calling)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:my name is|this is)\b.{0,40}\b(?:speaking|calling from|with)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhow (?:may|can) I (?:help|assist) you(?: today)?\b", re.IGNORECASE),
    re.compile(r"\b(?:you've reached|you have reached)\b", re.IGNORECASE),
    re.compile(
        r"\bwelcome to\b.{0,40}\b(?:support|customer service|billing|help desk)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:can|could|may) I (?:please )?verify\b", re.IGNORECASE),
    re.compile(r"\b(?:for security|for verification)(?: purposes)?\b", re.IGNORECASE),
    re.compile(r"\b(?:please )?(?:confirm|verify) (?:your )?(?:full )?name\b", re.IGNORECASE),
    re.compile(
        r"\b(?:please )?(?:confirm|verify|provide) (?:your )?(?:date of birth|dob|address|email|"
        r"phone(?: number)?|account number|last four|ssn|social security)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bI(?:'m| am) (?:going to|gonna) (?:need to )?authenticate\b", re.IGNORECASE),
    re.compile(r"\bI(?:'d| would) be happy to (?:help|assist)\b", re.IGNORECASE),
    re.compile(r"\blet me (?:check|look(?: that)? up|pull up|review|transfer)\b", re.IGNORECASE),
    re.compile(
        r"\bI(?:'m| am) (?:looking|pulling) (?:that|your (?:account|order|case)) up\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bI(?:'m| am) (?:showing|seeing) (?:here )?(?:that|on (?:my|the) (?:end|screen))\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:one moment|just a moment|bear with me)(?: please)?\b", re.IGNORECASE),
    re.compile(
        r"\bI(?:'ll| will) (?:go ahead and )?(?:escalate|transfer) (?:you|this)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bis there anything else I (?:can|may) (?:help|assist) (?:you )?with\b",
        re.IGNORECASE,
    ),
]

_CUSTOMER_PATTERNS = [
    re.compile(r"\bI(?:'m| am) calling (?:about|regarding|because)\b", re.IGNORECASE),
    re.compile(
        r"\bI(?:'d| would) like to (?:check|ask about|inquire about|know)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:what(?:'s| is)|where is) (?:my|the) (?:order|refund|payment|shipment|package|ticket|case)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:can|could) you (?:check|look up|tell me) (?:on )?my (?:account|order|bill|balance)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bI (?:haven'?t|have not) received\b", re.IGNORECASE),
    re.compile(
        r"\bI(?:'m| am) (?:having|experiencing) (?:a |an )?(?:problem|issue|trouble)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:this|that) (?:is|has been) (?:really )?(?:frustrating|unacceptable|ridiculous)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bI(?:'ve| have) been (?:waiting|trying|on hold)\b", re.IGNORECASE),
    re.compile(r"\b(?:nobody|no one) (?:has )?(?:helped|called|gotten back)\b", re.IGNORECASE),
    re.compile(r"\bI want to (?:speak|talk) to (?:a |your )?manager\b", re.IGNORECASE),
    re.compile(r"\bthis (?:doesn'?t|does not) work\b", re.IGNORECASE),
    re.compile(r"\bI (?:was )?charged\b", re.IGNORECASE),
    re.compile(
        r"\b(?:unauthorized|unexpected|incorrect|wrong) (?:charge|fee|payment|amount)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:double[- ]charged|overcharged)\b", re.IGNORECASE),
    re.compile(r"\bI(?:'d| would) like (?:a |my )?refund\b", re.IGNORECASE),
    re.compile(r"\bwhy (?:was|am) I (?:billed|charged)\b", re.IGNORECASE),
    re.compile(
        r"\bmy (?:bill|invoice|statement) (?:is|looks) (?:wrong|incorrect|too high)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bI(?:'d| would) like to cancel\b", re.IGNORECASE),
    re.compile(
        r"\b(?:please )?cancel (?:my )?(?:subscription|membership|service|account|order)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bI want to (?:cancel|close) (?:my )?(?:account|subscription|membership|service)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bstop (?:charging|billing) me\b", re.IGNORECASE),
]

# ASR tags, YouTube footers, non-speech labels, then collapsed repeats (spec).
_ASR_TAG = re.compile(
    r"\[(?:BLANK_?AUDIO|MUSIC|APPLAUSE|LAUGHTER|SILENCE|INAUDIBLE)\]"
    r"|\((?:music|applause|laughter|silence|inaudible)\)",
    re.IGNORECASE,
)
_DOTS = re.compile(r"\.{4,}")
_YT_FOOTER = re.compile(r"thanks for watching\.?", re.IGNORECASE)
_NONSPEECH = re.compile(
    r"^\s*(?:music|applause|laughter|silence|blank audio)[.!]?\s*$", re.IGNORECASE
)
_REPEATED_PHRASE = re.compile(r"\b(.{3,40}?)(?:\s+\1){2,}\b", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SHORT_ACK_WORDS = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "correct",
        "right",
        "okay",
        "ok",
        "sure",
        "absolutely",
        "exactly",
        "no",
        "nope",
    }
)
_INTERROGATIVE_START = re.compile(
    r"^(?:who|what|where|when|why|how|can|could|would|will|is|are|do|does|did|"
    r"may|should|shall|have|has|am)\b",
    re.IGNORECASE,
)


def _clean_transcript_text(text: str, *, whole_segment: bool = True) -> str:
    """Strip ASR artifacts per Milestone 3 spec."""
    cleaned = _ASR_TAG.sub("", text)
    cleaned = _DOTS.sub("...", cleaned)
    cleaned = _YT_FOOTER.sub("", cleaned)
    if whole_segment:
        cleaned = _NONSPEECH.sub("", cleaned)
    cleaned = _REPEATED_PHRASE.sub(r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _segment_confidence(avg_logprob: float, no_speech_prob: float) -> float:
    logprob_conf = max(0.0, min(1.0, 1.0 + avg_logprob))
    speech_conf = 1.0 - no_speech_prob
    return round(logprob_conf * 0.7 + speech_conf * 0.3, 4)


def _get_whisper_model() -> WhisperModel:
    global _model, _model_size, _LAST_WHISPER_INIT_SEC
    requested_size = (config or load_config(require_provider_key=False)).whisper_model_size
    if _model is not None and _model_size == requested_size:
        _LAST_WHISPER_INIT_SEC = 0.0
        return _model
    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False
    device = "cuda" if cuda_available else "cpu"
    compute_type = "float16" if cuda_available else "int8"
    t0 = time.perf_counter()
    _model = WhisperModel(requested_size, device=device, compute_type=compute_type)
    _LAST_WHISPER_INIT_SEC = time.perf_counter() - t0
    _model_size = requested_size
    logging.getLogger(__name__).info(
        "Speech model loaded",
        extra={"model": requested_size, "duration_ms": round(_LAST_WHISPER_INIT_SEC * 1000)},
    )
    return _model


def _compute_audio_hash(audio_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(audio_path, "rb") as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _cache_row_key(content_hash: str, backend: str | None = None) -> str:
    """String(64) lookup key: file SHA-256 plus diarization backend.

    Content hash stays the spec 8 KB SHA-256. Mixing in backend prevents a
    heuristic row from being returned when DIARIZATION_BACKEND=hybrid.
    """
    be = (backend or _diarization_backend()).strip().lower()
    return hashlib.sha256(f"{content_hash}:{be}".encode()).hexdigest()


def _check_cache(audio_hash: str) -> TranscriptionResult | None:
    row_key = _cache_row_key(audio_hash)
    with session_scope() as session:
        row = session.scalar(
            select(TranscriptionCache).where(TranscriptionCache.audio_hash == row_key)
        )
        if row is None:
            return None
        return TranscriptionResult.model_validate_json(row.transcription_json)


def _save_cache(audio_hash: str, result: TranscriptionResult) -> None:
    row_key = _cache_row_key(audio_hash)
    try:
        with session_scope() as session:
            session.add(
                TranscriptionCache(
                    audio_hash=row_key,
                    transcription_json=result.model_dump_json(),
                )
            )
    except IntegrityError:
        return


def get_last_transcription_diagnostics() -> dict | None:
    return _LAST_DIAGNOSTICS


def _diarization_backend() -> str:
    return os.getenv("DIARIZATION_BACKEND", "hybrid").strip().lower()


def _audio_duration_sec(path: Path) -> float:
    try:
        import librosa

        return float(librosa.get_duration(path=str(path)))
    except Exception:  # noqa: BLE001
        return 0.0


class SpeakerDiarizer:
    """Milestone 3 heuristic Agent/Customer assigner (baseline / compatibility).

    Silence / question / affirmation switches are kept. FALLBACK continues only
    from the last exclusive-pattern speaker so a weak DEFAULT_AGENT guess cannot
    cascade. Switches do not rewrite that pattern anchor.
    """

    def __init__(self) -> None:
        self.previous_speaker = None
        self.previous_segment = None
        self.last_confident_speaker: str | None = None
        self._AGENT_PATTERNS = _AGENT_PATTERNS
        self._CUSTOMER_PATTERNS = _CUSTOMER_PATTERNS

    def assign_speaker(self, segment) -> str:
        text = segment.text.strip()
        gap = None
        if self.previous_segment is not None:
            gap = segment.start - self.previous_segment.end

        agent_match = any(p.search(text) for p in self._AGENT_PATTERNS)
        customer_match = any(p.search(text) for p in self._CUSTOMER_PATTERNS)

        if agent_match and not customer_match:
            current_speaker = "Agent"
            reason = "AGENT_PATTERN"
            self.last_confident_speaker = "Agent"
        elif customer_match and not agent_match:
            current_speaker = "Customer"
            reason = "CUSTOMER_PATTERN"
            self.last_confident_speaker = "Customer"
        elif self.previous_segment is None:
            current_speaker = "Agent"
            reason = "DEFAULT_AGENT"
        else:
            previous_text = self.previous_segment.text.strip()
            if gap is not None and gap > 1.2:
                current_speaker = self._switch_speaker()
                reason = "SILENCE_GAP"
            elif previous_text.endswith("?"):
                current_speaker = self._switch_speaker()
                reason = "QUESTION_SWITCH"
            elif (
                len(text.split()) <= 3
                and len(previous_text.split()) > 10
                and text.lower().strip(".,!? ") in _SHORT_ACK_WORDS
            ):
                current_speaker = self._switch_speaker()
                reason = "AFFIRMATION_SWITCH"
            elif self.last_confident_speaker is not None:
                current_speaker = self.last_confident_speaker
                reason = "FALLBACK"
            else:
                current_speaker = "Ambiguous"
                reason = "FALLBACK_NO_ANCHOR"

        if os.getenv("DIARIZATION_DEBUG", "").strip():
            print(
                f"[{segment.start:.2f}s] "
                f"{current_speaker:<8} "
                f"Rule: {reason:<20} "
                f"Previous: {self.previous_speaker} "
                f"Confident: {self.last_confident_speaker} "
                f"Agent match: {agent_match} "
                f"Customer match: {customer_match} "
                f"Gap: {gap if self.previous_segment else 'N/A'} "
                f"Text: {text}"
            )
        self.previous_segment = segment
        self.previous_speaker = current_speaker
        return current_speaker

    def _switch_speaker(self) -> str:
        base = self.previous_speaker or self.last_confident_speaker
        if base == "Agent":
            return "Customer"
        return "Agent"


@dataclass(frozen=True)
class _SentenceUnit:
    start: float
    end: float
    text: str
    pattern_label: str | None
    word_count: int
    act: str  # "question" | "ack" | "statement"
    avg_logprob: float
    no_speech_prob: float


def _pattern_label(text: str) -> str | None:
    agent = any(p.search(text) for p in _AGENT_PATTERNS)
    customer = any(p.search(text) for p in _CUSTOMER_PATTERNS)
    if agent and not customer:
        return "Agent"
    if customer and not agent:
        return "Customer"
    return None


def _dialogue_act(text: str, word_count: int) -> str:
    """Structural dialogue act only — no domain lexicon."""
    stripped = text.rstrip()
    ack = text.lower().strip(".,!? ")
    if stripped.endswith("?") or _INTERROGATIVE_START.match(stripped):
        return "question"
    if word_count <= 3 and ack in _SHORT_ACK_WORDS:
        return "ack"
    return "statement"


def _allocate_sentence_times(
    parts: list[str],
    seg_start: float,
    seg_end: float,
    word_timings: list[tuple[str, float, float]],
) -> list[tuple[float, float]]:
    """Map sentence strings onto [start, end] using word timestamps when possible."""
    if len(parts) == 1:
        return [(seg_start, seg_end)]
    if word_timings:
        spans: list[tuple[float, float]] = []
        wi = 0
        for part in parts:
            need = re.sub(r"[^a-z0-9]+", "", part.lower())
            if not need:
                t = word_timings[min(wi, len(word_timings) - 1)][1]
                spans.append((t, t))
                continue
            start = word_timings[wi][1] if wi < len(word_timings) else seg_start
            end = start
            got = ""
            while wi < len(word_timings) and len(got) < len(need):
                tok, ws, we = word_timings[wi]
                if not got:
                    start = ws
                got += re.sub(r"[^a-z0-9]+", "", tok.lower())
                end = we
                wi += 1
            spans.append((start, max(end, start)))
        if spans:
            spans[0] = (seg_start, spans[0][1])
            spans[-1] = (spans[-1][0], seg_end)
        return spans
    total = sum(len(p) for p in parts) or 1
    dur = max(seg_end - seg_start, 1e-3)
    out: list[tuple[float, float]] = []
    cur = seg_start
    for i, part in enumerate(parts):
        share = dur * (len(part) / total)
        end = seg_end if i == len(parts) - 1 else cur + share
        out.append((cur, end))
        cur = end
    return out


def _sentence_units_from_whisper(whisper_segments) -> list[_SentenceUnit]:
    """Pass 1: split ASR segments into sentences with pattern + dialogue-act tags."""
    units: list[_SentenceUnit] = []
    for seg in whisper_segments:
        raw = (seg.text or "").strip()
        if not raw:
            continue
        parts = [p.strip() for p in _SENTENCE_SPLIT.split(raw) if p.strip()]
        if not parts:
            continue
        word_timings: list[tuple[str, float, float]] = []
        if getattr(seg, "words", None):
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                tok = (w.word or "").strip()
                if tok:
                    word_timings.append((tok, float(w.start), float(w.end)))
        spans = _allocate_sentence_times(parts, float(seg.start), float(seg.end), word_timings)
        avg_lp_raw = getattr(seg, "avg_logprob", None)
        avg_lp = float(avg_lp_raw) if avg_lp_raw is not None else -0.5
        nsp_raw = getattr(seg, "no_speech_prob", None)
        nsp = float(nsp_raw) if nsp_raw is not None else 0.0
        for part, (t0, t1) in zip(parts, spans):
            text = _clean_transcript_text(part)
            if not text:
                continue
            wc = len(text.split())
            units.append(
                _SentenceUnit(
                    start=t0,
                    end=t1,
                    text=text,
                    pattern_label=_pattern_label(text),
                    word_count=wc,
                    act=_dialogue_act(text, wc),
                    avg_logprob=avg_lp,
                    no_speech_prob=nsp,
                )
            )
    return units


def _opposite(label: str) -> str:
    return "Customer" if label == "Agent" else "Agent"


def _dialogue_act_labels(units: list[_SentenceUnit]) -> list[str]:
    """Pass 2–3: adjacency matching + pattern-anchored FALLBACK."""
    if not units:
        return []

    labels: list[str] = []
    last_pinned: str | None = None
    debug = bool(os.getenv("DIARIZATION_DEBUG", "").strip())

    for i, unit in enumerate(units):
        reason: str
        if unit.pattern_label is not None:
            labels.append(unit.pattern_label)
            last_pinned = unit.pattern_label
            reason = "PATTERN"
        elif i == 0:
            labels.append("Agent")
            reason = "DEFAULT_AGENT"
        else:
            prev = units[i - 1]
            prev_lab = labels[i - 1]
            gap = unit.start - prev.end

            if prev.act == "question":
                labels.append(_opposite(prev_lab))
                reason = "QUESTION_SWITCH"
            elif prev.word_count > 10 and unit.act == "ack":
                labels.append(_opposite(prev_lab))
                reason = "AFFIRMATION_SWITCH"
            elif gap > 1.2:
                labels.append(_opposite(prev_lab))
                reason = "SILENCE_GAP"
            elif (
                # Short reply then a tight follow-up question = same speaker
                # continuing (e.g. "I did." → "Do you need the customer number?").
                prev.word_count <= 3
                and prev.act == "statement"
                and unit.act == "question"
                and gap <= 0.75
            ):
                labels.append(prev_lab)
                reason = "SHORT_REPLY_CONTINUE"
            elif last_pinned is not None:
                labels.append(last_pinned)
                reason = "FALLBACK_PINNED"
            else:
                labels.append(prev_lab)
                reason = "FALLBACK_PREV"

        if debug:
            gap_s = f"{unit.start - units[i - 1].end:.2f}" if i > 0 else "N/A"
            print(
                f"[{unit.start:.2f}s] "
                f"{labels[-1]:<8} "
                f"Rule: {reason:<20} "
                f"Pinned: {last_pinned} "
                f"Gap: {gap_s} "
                f"Act: {unit.act} "
                f"Text: {unit.text}"
            )

    return labels


def _merge_same_speaker(
    units: list[_SentenceUnit], labels: list[str]
) -> list[TranscriptionSegment]:
    """Collapse consecutive same-speaker sentences into output segments."""
    if not units:
        return []
    out: list[TranscriptionSegment] = []
    buf_text = [units[0].text]
    start = units[0].start
    end = units[0].end
    speaker = labels[0]
    avg_lp = units[0].avg_logprob
    nsp = units[0].no_speech_prob
    count = 1

    def flush() -> None:
        nonlocal buf_text, start, end, speaker, avg_lp, nsp, count
        conf = _segment_confidence(avg_lp / count, nsp / count)
        out.append(
            TranscriptionSegment(
                start_time=start,
                end_time=end,
                text=" ".join(buf_text).strip(),
                speaker=speaker,
                confidence=conf,
            )
        )

    for unit, lab in zip(units[1:], labels[1:]):
        gap = unit.start - end
        if lab == speaker and gap <= 0.75:
            buf_text.append(unit.text)
            end = unit.end
            avg_lp += unit.avg_logprob
            nsp += unit.no_speech_prob
            count += 1
            continue
        flush()
        buf_text = [unit.text]
        start = unit.start
        end = unit.end
        speaker = lab
        avg_lp = unit.avg_logprob
        nsp = unit.no_speech_prob
        count = 1
    flush()
    return out


def _run_heuristic(whisper_segments) -> list[TranscriptionSegment]:
    """Sentence split + dialogue-act adjacency + pattern-anchored FALLBACK."""
    units = _sentence_units_from_whisper(whisper_segments)
    labels = _dialogue_act_labels(units)
    return _merge_same_speaker(units, labels)


def _run_heuristic_with_diagnostics(
    whisper_segments,
) -> tuple[list[TranscriptionSegment], dict]:
    t0 = time.perf_counter()
    segments = _run_heuristic(whisper_segments)
    return segments, {
        "backend": "heuristic",
        "ok": True,
        "label_source": "heuristic",
        "acoustic_verified": False,
        "note": "sentence split + dialogue-act adjacency + pattern-anchored FALLBACK",
        "segment_count": len(segments),
        "heuristic_diarize_sec": round(time.perf_counter() - t0, 3),
    }


def _words_and_spans_from_whisper(
    whisper_segments,
) -> tuple[list[WordTiming], list[tuple[float, float]]]:
    words: list[WordTiming] = []
    asr_spans: list[tuple[float, float]] = []
    for seg in whisper_segments:
        asr_spans.append((float(seg.start), float(seg.end)))
        if not _clean_transcript_text(seg.text):
            continue
        if seg.words:
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                token = _clean_transcript_text(w.word, whole_segment=False)
                if not token:
                    continue
                words.append(WordTiming(token, float(w.start), float(w.end)))
        else:
            text = _clean_transcript_text(seg.text)
            if text:
                words.append(WordTiming(text, float(seg.start), float(seg.end)))
    return words, asr_spans


def _segments_from_acoustic_dicts(rows: list[dict]) -> list[TranscriptionSegment]:
    return [
        TranscriptionSegment(
            start_time=float(r["start"]),
            end_time=float(r["end"]),
            text=r["text"],
            speaker=r["speaker"],
            confidence=float(r["confidence"]),
        )
        for r in rows
        if (r.get("text") or "").strip()
    ]


def _call_acoustic(
    audio_path: Path,
    whisper_segments,
    *,
    timeout_sec: float,
) -> tuple[list[TranscriptionSegment], dict]:
    words, asr_spans = _words_and_spans_from_whisper(whisper_segments)
    rows, diagnostics = run_acoustic_diarization(
        audio_path, words, asr_spans, timeout_sec=timeout_sec
    )
    segments = _segments_from_acoustic_dicts(rows)
    diagnostics = dict(diagnostics)
    diagnostics["segment_count"] = len(segments)
    return segments, diagnostics


def _timing_base(
    *,
    whisper_init_sec: float,
    whisper_transcribe_sec: float,
    t_total: float,
    duration_sec: float | None = None,
    diagnostics: dict | None = None,
    timeout_sec: float | None = None,
) -> dict:
    stage = (diagnostics or {}).get("timing_sec") or {}
    out = {
        "whisper_model_init": round(whisper_init_sec, 3),
        "whisper_transcribe": round(whisper_transcribe_sec, 3),
        "total_run_transcription": round(time.perf_counter() - t_total, 3),
    }
    if duration_sec is not None:
        out["audio_duration_sec"] = round(duration_sec, 3)
    if timeout_sec is not None:
        out["acoustic_timeout_sec"] = (diagnostics or {}).get(
            "acoustic_timeout_sec", round(timeout_sec, 3)
        )
    if stage:
        out["community1_device"] = stage.get("community1_device")
        out["community1_pipeline_init"] = stage.get("community1_pipeline_init")
        out["community1_inference"] = stage.get("community1_inference")
        out["align_group_role"] = stage.get("align_group_role")
    heur = (diagnostics or {}).get("heuristic_diarize_sec")
    if heur is not None:
        out["heuristic_diarize"] = heur
    return out


def run_transcription(intake_result: IntakeResult) -> TranscriptionResult:
    global _LAST_DIAGNOSTICS

    if not intake_result.validation_passed:
        raise ValueError("cannot transcribe invalid audio")
    if not intake_result.temp_file_path:
        raise ValueError("cannot transcribe invalid audio file")

    audio_path = Path(intake_result.temp_file_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    init_db()
    audio_hash = _compute_audio_hash(audio_path)
    cached = _check_cache(audio_hash)
    if cached is not None:
        backend = _diarization_backend()
        # Cache stores labels only — report requested backend so logs/UI do not
        # inherit diagnostics from a prior run of a different approach.
        _LAST_DIAGNOSTICS = {
            "backend": backend,
            "ok": True,
            "cache_hit": True,
            "label_source": backend if backend in {"heuristic", "acoustic"} else "cached",
            "segment_count": len(cached.segments),
            "note": "served from TranscriptionCache",
        }
        print(
            f"[transcription] backend={backend} segments={len(cached.segments)} "
            f"ok=True label_source={_LAST_DIAGNOSTICS['label_source']} "
            f"fallback=None cache_hit=True"
        )
        return _quality_flags(cached.model_copy(update={"call_id": intake_result.call_id}))

    t_total = time.perf_counter()
    model = _get_whisper_model()
    whisper_init_sec = float(_LAST_WHISPER_INIT_SEC or 0.0)

    t_asr = time.perf_counter()
    whisper_segments, _info = model.transcribe(
        audio=str(audio_path),
        beam_size=1,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    whisper_segments = list(whisper_segments)
    whisper_transcribe_sec = time.perf_counter() - t_asr

    backend = _diarization_backend()
    duration_sec = _audio_duration_sec(audio_path)

    if backend == "heuristic":
        result_segments, diagnostics = _run_heuristic_with_diagnostics(whisper_segments)
        diagnostics["timing_sec"] = _timing_base(
            whisper_init_sec=whisper_init_sec,
            whisper_transcribe_sec=whisper_transcribe_sec,
            t_total=t_total,
            diagnostics=diagnostics,
        )
    elif backend == "acoustic":
        timeout_sec = acoustic_timeout_sec(duration_sec)
        try:
            result_segments, diagnostics = _call_acoustic(
                audio_path, whisper_segments, timeout_sec=timeout_sec
            )
        except TimeoutError as exc:
            _LAST_DIAGNOSTICS = {
                "backend": "acoustic",
                "ok": False,
                "error": str(exc),
                "fallback_activated": False,
            }
            raise AcousticDiarizationError(str(exc)) from exc
        except Exception as exc:
            if isinstance(exc, AcousticDiarizationError):
                _LAST_DIAGNOSTICS = {
                    "backend": "acoustic",
                    "ok": False,
                    "error": str(exc),
                }
                raise
            _LAST_DIAGNOSTICS = {"backend": "acoustic", "ok": False, "error": str(exc)}
            raise AcousticDiarizationError(str(exc)) from exc
        diagnostics["backend"] = "acoustic"
        diagnostics["timing_sec"] = _timing_base(
            whisper_init_sec=whisper_init_sec,
            whisper_transcribe_sec=whisper_transcribe_sec,
            t_total=t_total,
            duration_sec=duration_sec,
            diagnostics=diagnostics,
            timeout_sec=timeout_sec,
        )
    elif backend == "hybrid":
        timeout_sec = acoustic_timeout_sec(duration_sec)
        try:
            result_segments, diagnostics = _call_acoustic(
                audio_path, whisper_segments, timeout_sec=timeout_sec
            )
            diagnostics["backend"] = "hybrid"
            diagnostics["primary_path"] = "acoustic"
        except TimeoutError as exc:
            result_segments, diagnostics = _run_heuristic_with_diagnostics(whisper_segments)
            diagnostics.update(
                {
                    "backend": "hybrid",
                    "primary_path": "heuristic_fallback",
                    "fallback_activated": True,
                    "fallback_reason": f"acoustic_timeout: {exc}",
                    "acoustic_verified": False,
                    "label_source": "heuristic_fallback",
                    "acoustic_timeout_sec": round(timeout_sec, 3),
                }
            )
        except Exception as exc:  # noqa: BLE001
            result_segments, diagnostics = _run_heuristic_with_diagnostics(whisper_segments)
            diagnostics.update(
                {
                    "backend": "hybrid",
                    "primary_path": "heuristic_fallback",
                    "fallback_activated": True,
                    "fallback_reason": f"acoustic_error: {type(exc).__name__}: {exc}",
                    "acoustic_verified": False,
                    "label_source": "heuristic_fallback",
                    "acoustic_timeout_sec": round(timeout_sec, 3),
                }
            )
        diagnostics["segment_count"] = len(result_segments)
        diagnostics["timing_sec"] = _timing_base(
            whisper_init_sec=whisper_init_sec,
            whisper_transcribe_sec=whisper_transcribe_sec,
            t_total=t_total,
            duration_sec=duration_sec,
            diagnostics=diagnostics,
            timeout_sec=timeout_sec,
        )
    else:
        raise ValueError(
            f"Unknown DIARIZATION_BACKEND={backend!r}. Use 'hybrid', 'acoustic', or 'heuristic'."
        )

    full_text = " ".join(s.text.strip() for s in result_segments if s.text.strip())
    _LAST_DIAGNOSTICS = diagnostics
    timing = diagnostics.get("timing_sec") or {}
    print(
        f"[transcription] backend={backend} segments={len(result_segments)} "
        f"ok={diagnostics.get('ok')} "
        f"label_source={diagnostics.get('label_source')} "
        f"fallback={diagnostics.get('fallback_activated')} "
        f"cache_hit=False "
        f"total_sec={timing.get('total_run_transcription')}"
    )
    result = TranscriptionResult(
        call_id=intake_result.call_id,
        full_text=full_text,
        segments=result_segments,
        language="en",
    )
    _save_cache(audio_hash, result)
    return _quality_flags(result)


def _quality_flags(result: TranscriptionResult) -> TranscriptionResult:
    settings = load_config(require_provider_key=False)
    ratio = (
        sum(segment.confidence < settings.confidence_threshold for segment in result.segments)
        / len(result.segments)
        if result.segments
        else 1.0
    )
    return result.model_copy(
        update={
            "low_confidence_ratio": ratio,
            "flagged_for_review": ratio > settings.low_confidence_halt_ratio,
        }
    )
