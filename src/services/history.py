from __future__ import annotations

import json

from sqlalchemy import select

from src.database.connection import session_scope
from src.database.models import CallAnalysis
from src.database.repository import get_call_analysis
from src.graph.state import CallReport
from src.services.pipeline import PipelineResult, _write_temp
from src.services.report_generator import report_to_json, report_to_pdf
from src.utils.formatters import format_qa, format_summary, secs_to_mmss


def history_rows():
    with session_scope() as session:
        analyses = session.scalars(
            select(CallAnalysis).order_by(CallAnalysis.created_at.desc())
        ).all()
        rows = []
        for item in analyses:
            summary, qa = json.loads(item.summary_json), json.loads(item.qa_json)
            rows.append(
                [
                    item.call_id,
                    item.created_at.strftime("%Y-%m-%d %H:%M"),
                    summary["call_purpose"],
                    qa["overall_score"],
                    "Needs review"
                    if any(flag["severity"] == "critical" for flag in qa["compliance_flags"])
                    else "Completed",
                ]
            )
        return rows


def history_report(call_id: str | None) -> PipelineResult:
    if not call_id:
        return PipelineResult(ok=False, status_md="Select a stored call.")
    analysis = get_call_analysis(call_id)
    if analysis is None:
        return PipelineResult(ok=False, status_md="This call is no longer available.")
    report = CallReport.model_validate_json(analysis.report_json)
    name = f"CallReview_{report.created_at:%Y-%m-%d_%H-%M-%S}_{report.call_id[:8]}"
    return PipelineResult(
        ok=True,
        status_md="### Stored call review",
        call_meta_md=f"**Call {report.call_id[:8]}** · {secs_to_mmss(report.intake.audio_properties.duration_seconds)} · {report.qa_scores.overall_score:.2f}/5 QA",
        transcript="\n\n".join(
            f"[{secs_to_mmss(s.start_time)}-{secs_to_mmss(s.end_time)}] {s.speaker}: {s.text}"
            for s in report.transcription.segments
        ),
        summary_md=format_summary(report.summary),
        qa_md=format_qa(report.qa_scores),
        pdf_path=_write_temp(".pdf", report_to_pdf(report), name),
        json_path=_write_temp(".json", report_to_json(report).encode(), name),
    )
