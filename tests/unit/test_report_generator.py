import json

from src.services.report_generator import build_report, report_to_json, report_to_pdf
from tests.unit.test_graph_event_logging import _intake, _qa, _summary, _transcription


def test_report_outputs_json_and_pdf():
    summary = _summary()
    summary.call_purpose = "Customer said <b>billing</b>"
    report = build_report(
        intake=_intake(),
        transcription=_transcription(),
        summary=summary,
        qa_scores=_qa(),
    )

    data = json.loads(report_to_json(report))
    pdf = report_to_pdf(report)

    assert data["call_id"] == "call-1"
    assert data["summary"]["call_purpose"] == "Customer said <b>billing</b>"
    assert pdf.startswith(b"%PDF-")
