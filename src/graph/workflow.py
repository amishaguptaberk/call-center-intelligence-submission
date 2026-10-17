import logging
import time
from functools import wraps
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    error_node,
    injection_detection_node,
    intake_node,
    pii_redaction_node,
    qa_node,
    report_node,
    summarization_node,
    supervisor_review_node,
    transcription_node,
)
from src.graph.state import PipelineState

logger = logging.getLogger(__name__)


class StageFailure(Exception):
    def __init__(self, stage, error):
        self.stage = stage
        self.error_type = type(error).__name__
        super().__init__(f"{stage} failed ({self.error_type}). Please retry the analysis.")


def observed(stage, function):
    @wraps(function)
    def invoke(state):
        started = time.monotonic()
        logger.info("Stage started", extra={"node": stage})
        try:
            result = function(state)
        except Exception as exc:
            logger.error("Stage failed", extra={"node": stage, "error_type": type(exc).__name__})
            raise StageFailure(stage, exc) from exc
        logger.info(
            "Stage completed",
            extra={"node": stage, "duration_ms": round((time.monotonic() - started) * 1000)},
        )
        return result

    return invoke


def route_after_intake(state: PipelineState) -> str:
    if state["intake"].validation_passed:
        return "transcription"
    return "error"


def route_after_injection(state: PipelineState) -> str:
    if state["injection_scan"].injection_detected:
        return "error"
    return "pii_redaction"


def route_after_qa(state: PipelineState) -> str:
    if any(flag.severity == "critical" for flag in state["qa_scores"].compliance_flags):
        return "supervisor_review"

    return "report"


workflow = StateGraph(PipelineState)

workflow.add_node("intake", observed("intake", intake_node))
workflow.add_node("transcription", observed("transcription", transcription_node))
workflow.add_node("injection_detection", observed("injection_detection", injection_detection_node))
workflow.add_node("pii_redaction", observed("pii_redaction", pii_redaction_node))
workflow.add_node("summarization", observed("summarization", summarization_node))
workflow.add_node("qa", observed("qa", qa_node))
workflow.add_node("report", observed("report", report_node))
workflow.add_node("error", error_node)
workflow.add_node("supervisor_review", observed("supervisor_review", supervisor_review_node))

workflow.add_edge(START, "intake")
workflow.add_conditional_edges("intake", route_after_intake)
workflow.add_conditional_edges(
    "transcription",
    lambda state: "error" if state.get("status") == "failed" else "injection_detection",
)
workflow.add_conditional_edges("injection_detection", route_after_injection)
workflow.add_edge("pii_redaction", "summarization")
workflow.add_edge("summarization", "qa")
workflow.add_conditional_edges("qa", route_after_qa)
workflow.add_edge("report", END)
workflow.add_edge("supervisor_review", END)
workflow.add_edge("error", END)

graph = workflow.compile()


def run_graph(state: PipelineState) -> PipelineState:
    current = dict(state)
    try:
        for chunk in graph.stream(state):
            for update in chunk.values():
                current.update(update)
        return current
    except Exception as exc:
        current["error"] = (
            str(exc)
            if isinstance(exc, StageFailure)
            else "Processing failed. Please retry the analysis."
        )
        current.update(error_node(current))
        return current
    finally:
        intake = current.get("intake")
        if intake and intake.temp_file_path:
            Path(intake.temp_file_path).unlink(missing_ok=True)
