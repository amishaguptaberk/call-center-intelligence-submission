from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from src.graph.state import (
    CallReport,
    IntakeResult,
    QAScoreResult,
    SummaryResult,
    TranscriptionResult,
)


def build_report(
    intake: IntakeResult,
    transcription: TranscriptionResult,
    summary: SummaryResult,
    qa_scores: QAScoreResult,
) -> CallReport:
    return CallReport(
        call_id=intake.call_id,
        intake=intake,
        transcription=transcription,
        summary=summary,
        qa_scores=qa_scores,
    )


def report_to_json(report: CallReport) -> str:
    return report.model_dump_json(indent=2)


def report_to_pdf(report: CallReport) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Call Analysis Report", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            f"<b>Call ID:</b> {_safe(report.call_id)}",
            styles["BodyText"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Created:</b> {_safe(str(report.created_at))}",
            styles["BodyText"],
        )
    )

    story.append(Spacer(1, 16))

    # Summary
    story.append(Paragraph("Summary", styles["Heading2"]))

    story.append(
        Paragraph(
            f"<b>Call Purpose:</b> {_safe(report.summary.call_purpose)}",
            styles["BodyText"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Resolution:</b> {report.summary.resolution_status.value}",
            styles["BodyText"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Sentiment:</b> {_safe(report.summary.sentiment_trajectory)}",
            styles["BodyText"],
        )
    )

    story.append(Spacer(1, 12))

    # Discussion points
    story.append(Paragraph("Key Discussion Points", styles["Heading2"]))

    for point in report.summary.key_discussion_points:
        story.append(
            Paragraph(
                f"• {_safe(point)}",
                styles["BodyText"],
            )
        )

    story.append(Spacer(1, 12))

    # Action items
    story.append(Paragraph("Action Items", styles["Heading2"]))

    if report.summary.action_items:
        for item in report.summary.action_items:
            text = f"• {_safe(item.description)} — Owner: {_safe(item.owner)}"

            if item.deadline:
                text += f" — Deadline: {_safe(item.deadline)}"

            story.append(Paragraph(text, styles["BodyText"]))
    else:
        story.append(Paragraph("No action items.", styles["BodyText"]))

    story.append(Spacer(1, 12))

    # QA
    story.append(Paragraph("QA Scores", styles["Heading2"]))

    for score in report.qa_scores.dimension_scores:
        story.append(
            Paragraph(
                f"<b>{score.dimension}:</b> {score.score}/5 — {_safe(score.justification)}",
                styles["BodyText"],
            )
        )
        if score.coaching_tip:
            label = "Keep doing" if score.score == 5 else "Coaching tip"
            story.append(
                Paragraph(f"<b>{label}:</b> {_safe(score.coaching_tip)}", styles["BodyText"])
            )

    story.append(
        Paragraph(
            f"<b>Overall Score:</b> {report.qa_scores.overall_score:.2f}/5",
            styles["BodyText"],
        )
    )

    story.append(Spacer(1, 12))

    # Compliance
    story.append(Paragraph("Compliance Flags", styles["Heading2"]))

    if report.qa_scores.compliance_flags:
        for flag in report.qa_scores.compliance_flags:
            story.append(
                Paragraph(
                    f"<b>{flag.severity.upper()}:</b> "
                    f"{_safe(flag.description)} "
                    f"({_safe(flag.timestamp_reference)})",
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "No compliance flags detected.",
                styles["BodyText"],
            )
        )

    story.append(Spacer(1, 12))

    # Transcript
    story.append(Paragraph("Transcript", styles["Heading2"]))

    for segment in report.transcription.segments:
        transcript_line = (
            f"<b>{segment.speaker}</b> "
            f"[{segment.start_time:.2f}–{segment.end_time:.2f}]: "
            f"{_safe(segment.text)}"
        )

        story.append(
            Paragraph(
                transcript_line,
                styles["BodyText"],
            )
        )

    document.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _safe(text: str) -> str:
    return escape(text, quote=False)
