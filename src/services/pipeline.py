from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import soundfile as sf

from src.graph.state import AudioInput
from src.services.report_generator import report_to_json, report_to_pdf
from src.utils.config import temp_file_retention
from src.utils.formatters import format_qa, format_summary, secs_to_mmss

_TEMP_FILES: list[Path] = []
_TEMP_LOCK = Lock()


@dataclass(frozen=True)
class PipelineResult:
    ok: bool
    status_md: str
    call_meta_md: str = ""
    transcript: str = ""
    summary_md: str = ""
    qa_md: str = ""
    pdf_path: str | None = None
    json_path: str | None = None


def process_call(audio, caller_id: str = "", department: str = "") -> PipelineResult:
    if audio is None:
        return _failure("Add a call recording before starting the analysis.")

    try:
        from src.graph.workflow import run_graph

        path = _audio_path(audio)
        state = run_graph(
            {
                "audio_input": AudioInput(
                    audio_data=path.read_bytes(),
                    filename=path.name,
                    caller_id=(caller_id or "").strip() or None,
                    department=(department or "").strip() or None,
                )
            }
        )
        if state.get("status") == "failed" or "report" not in state:
            intake = state.get("intake")
            message = getattr(intake, "validation_error", None) or state.get("error")
            scan = state.get("injection_scan")
            if scan and scan.injection_detected:
                message = (
                    "The transcript was held for review because it contained instruction-like content. Matched patterns: "
                    + ", ".join(scan.matched_patterns)
                )
            return _failure(message or "The call could not be analyzed. Try another recording.")

        report = state["report"]
        review = state.get("status") == "supervisor_review"
        export_name = f"CallReview_{report.created_at:%Y-%m-%d_%H-%M-%S}_{report.call_id[:8]}"
        pdf_path = _write_temp(".pdf", report_to_pdf(report), export_name)
        json_path = _write_temp(".json", report_to_json(report).encode(), export_name)
        duration = report.intake.audio_properties.duration_seconds
        return PipelineResult(
            ok=True,
            status_md=(
                "### ⚠ Supervisor review required\nA critical compliance finding needs human review."
                if review
                else "### ✓ Analysis complete\nThe call is ready for quality review."
            ),
            call_meta_md=(
                f"**Call {report.call_id[:8]}** · {secs_to_mmss(duration)} · "
                f"{len(report.transcription.segments)} transcript segments · "
                f"{report.qa_scores.overall_score:.2f}/5 QA"
            ),
            transcript="\n\n".join(
                f"[{secs_to_mmss(s.start_time)}–{secs_to_mmss(s.end_time)}] "
                f"{s.speaker}{' · LOW CONFIDENCE' if s.confidence < 0.6 else ''}\n{s.text.strip()}"
                for s in report.transcription.segments
                if s.text.strip()
            ),
            summary_md=format_summary(report.summary),
            qa_md=format_qa(report.qa_scores),
            pdf_path=pdf_path,
            json_path=json_path,
        )
    except Exception:  # noqa: BLE001 — UI boundary converts errors to safe copy
        return _failure("The call could not be analyzed. Check the recording and try again.")


def _audio_path(audio) -> Path:
    if isinstance(audio, (str, Path)):
        path = Path(audio)
        if not path.is_file():
            raise ValueError("The selected recording is no longer available.")
        return path
    if isinstance(audio, tuple) and len(audio) == 2:
        sample_rate, samples = audio
        descriptor, filename = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        path = Path(filename)
        try:
            sf.write(path, samples, sample_rate)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        _remember(path)
        return path
    raise ValueError("Use an uploaded file or microphone recording.")


def _write_temp(suffix: str, content: bytes, name: str) -> str:
    descriptor, filename = tempfile.mkstemp(prefix=f"{name}_", suffix=suffix)
    os.close(descriptor)
    path = Path(filename)
    path.write_bytes(content)
    _remember(path)
    return str(path)


def _remember(path: Path) -> None:
    with _TEMP_LOCK:
        _TEMP_FILES.append(path)
        while len(_TEMP_FILES) > temp_file_retention():
            stale = _TEMP_FILES.pop(0)
            stale.unlink(missing_ok=True)


def _failure(message: str) -> PipelineResult:
    return PipelineResult(
        ok=False,
        status_md=f"### Analysis needs attention\n{message}",
    )
