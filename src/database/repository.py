from src.database.connection import session_scope
from src.database.models import AuditLogEntry, CallAnalysis
from src.graph.state import CallReport


def save_call_analysis(
    report: CallReport, *, status: str = "completed", audio_filename: str | None = None
) -> None:
    with session_scope() as session:
        analysis = CallAnalysis(
            call_id=report.call_id,
            status=status,
            audio_filename=audio_filename,
            transcript_text=report.transcription.full_text,
            summary_json=report.summary.model_dump_json(),
            qa_json=report.qa_scores.model_dump_json(),
            report_json=report.model_dump_json(),
        )

        session.add(analysis)


def get_call_analysis(call_id: str) -> CallAnalysis | None:
    with session_scope() as session:
        analysis = session.query(CallAnalysis).filter(CallAnalysis.call_id == call_id).one_or_none()

        if analysis is not None:
            session.expunge(analysis)

        return analysis


def log_event(
    call_id: str,
    action: str,
    user: str = "system",
    details: str | None = None,
) -> None:
    with session_scope() as session:
        entry = AuditLogEntry(
            call_id=call_id,
            action=action,
            user=user,
            details=details,
        )

        session.add(entry)
