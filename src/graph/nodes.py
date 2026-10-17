from src.agents.intake import run_intake
from src.agents.qa_scoring import score_qa
from src.agents.summarization import summarize
from src.agents.transcription import run_transcription
from src.database.repository import save_call_analysis
from src.graph.state import CallReport, PipelineState
from src.security.audit import AuditLogger
from src.security.injection_detector import detect_injection
from src.security.pii_redactor import redact_pii, redact_segments
from src.services.report_generator import build_report

event_logger = AuditLogger()


def _log_event(state: PipelineState, action: str, stage: str, details: dict | None = None) -> None:
    call_id = _call_id(state)
    if call_id:
        event_logger.log(call_id, action, "system", details, stage=stage)


def _call_id(state: PipelineState) -> str | None:
    for key in (
        "intake",
        "sanitized_transcription",
        "transcription",
        "summary",
        "qa_scores",
        "report",
    ):
        item = state.get(key)
        if item is not None:
            call_id = getattr(item, "call_id", None)
            if isinstance(call_id, str) and call_id:
                return call_id
    return None


def intake_node(state: PipelineState):
    audio_input = state["audio_input"]
    result = run_intake(audio_input)
    event_logger.log(
        result.call_id,
        "started",
        "system",
        {
            "filename": audio_input.filename,
            "validation_passed": result.validation_passed,
        },
        stage="intake",
    )
    return {"intake": result}


def transcription_node(state: PipelineState) -> dict:
    intake_result = state["intake"]
    result = run_transcription(intake_result)
    if result.flagged_for_review:
        return {
            "transcription": result,
            "status": "failed",
            "error": "Transcription confidence is too low for reliable scoring. Review the recording or upload clearer audio.",
        }
    return {"transcription": result}


def injection_detection_node(state: PipelineState) -> dict:
    transcript = state["transcription"]
    result = detect_injection(transcript.full_text)

    return {
        "injection_scan": result,
    }


def pii_redaction_node(state: PipelineState) -> dict:
    transcript = state["transcription"]
    result = redact_pii(transcript.full_text)
    segment_texts, segments_have_pii = redact_segments(
        [segment.text for segment in transcript.segments]
    )
    safe_segments = [
        segment.model_copy(update={"text": redacted})
        for segment, redacted in zip(transcript.segments, segment_texts)
    ]
    sanitized = transcript.model_copy(
        update={
            "full_text": result.redacted_text,
            "segments": safe_segments,
        }
    )
    return {
        "sanitized_transcription": sanitized,
        "pii_result": result.model_copy(
            update={
                "pii_found": result.pii_found or segments_have_pii,
            }
        ),
    }


def summarization_node(state: PipelineState) -> dict:
    transcript = state["sanitized_transcription"]
    result = summarize(transcript)
    return {"summary": result}


def qa_node(state: PipelineState) -> dict:
    transcript = state["sanitized_transcription"]
    summary = state["summary"]
    result = score_qa(transcript=transcript, summary=summary)
    return {"qa_scores": result}


def report_node(state: PipelineState) -> dict:
    report = build_report(
        intake=state["intake"],
        transcription=state["sanitized_transcription"],
        summary=state["summary"],
        qa_scores=state["qa_scores"],
    )
    if isinstance(report, CallReport):
        audio = state.get("audio_input")
        save_call_analysis(report, audio_filename=audio.filename if audio else None)
    _log_event(
        {**state, "report": report},
        "completed",
        "report",
        _report_details(report),
    )

    return {
        "report": report,
        "status": "completed",
    }


def error_node(state: PipelineState) -> dict:
    _log_event(state, "failed", "error", _failure_details(state))
    return {
        "status": "failed",
    }


def supervisor_review_node(state: PipelineState) -> dict:
    report = build_report(
        intake=state["intake"],
        transcription=state["sanitized_transcription"],
        summary=state["summary"],
        qa_scores=state["qa_scores"],
    )
    if isinstance(report, CallReport):
        audio = state.get("audio_input")
        save_call_analysis(
            report, status="flagged_for_review", audio_filename=audio.filename if audio else None
        )
    _log_event(
        {**state, "report": report},
        "flagged_for_review",
        "qa",
        {
            "critical_flags": [
                flag.description
                for flag in state.get("qa_scores", ()).compliance_flags
                if flag.severity == "critical"
            ]
        }
        if state.get("qa_scores")
        else None,
    )
    return {
        "status": "supervisor_review",
        "report": report,
    }


def _failure_details(state: PipelineState) -> dict:
    details = {}
    intake = state.get("intake")
    if intake and intake.validation_error:
        details["validation_error"] = intake.validation_error
    scan = state.get("injection_scan")
    if scan and scan.injection_detected:
        details["matched_patterns"] = scan.matched_patterns
    if state.get("error"):
        details["error"] = state["error"]
    return details


def _report_details(report) -> dict:
    flags = getattr(report.qa_scores, "compliance_flags", [])
    overall_score = getattr(report.qa_scores, "overall_score", None)
    return {
        "overall_score": overall_score if isinstance(overall_score, int | float) else None,
        "compliance_flags": len(flags) if isinstance(flags, list) else 0,
    }
