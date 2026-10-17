"""Opt-in live provider check using only a synthetic, PII-free conversation."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.agents.qa_scoring import DIMENSION_WEIGHTS, score_qa
from src.agents.summarization import summarize
from src.graph.state import TranscriptionResult, TranscriptionSegment
from src.utils.config import load_config

config = replace(load_config(), max_retries_per_node=1, llm_timeout_seconds=20)
turns = [
    ("Customer", "What time does your store close on weekdays?"),
    ("Agent", "We close at six in the evening Monday through Friday."),
    ("Customer", "That answers my question. Thank you."),
    ("Agent", "You are welcome. Have a good day."),
]
transcript = TranscriptionResult(
    call_id="milestone4-smoke",
    full_text=" ".join(text for _, text in turns),
    language="en",
    segments=[
        TranscriptionSegment(
            start_time=i * 4,
            end_time=i * 4 + 3,
            speaker=speaker,
            text=text,
            confidence=1,
        )
        for i, (speaker, text) in enumerate(turns)
    ],
)
evidence = {
    "provider": config.llm_provider,
    "model_override": config.llm_model,
    "synthetic_input": True,
    "attempts_per_agent": 1,
    "timeout_seconds": 20,
}
try:
    with (
        patch("src.agents.summarization.load_config", return_value=config),
        patch("src.agents.qa_scoring.load_config", return_value=config),
    ):
        summary = summarize(transcript)
        evidence["summary_valid"] = True
        qa = score_qa(transcript, summary)
    assert summary.call_id == qa.call_id == transcript.call_id
    assert qa.overall_score == round(
        sum(DIMENSION_WEIGHTS[d.dimension] * d.score for d in qa.dimension_scores), 2
    )
    evidence.update(
        status="passed",
        identity_preserved=True,
        dimensions=len(qa.dimension_scores),
        weighted_score=qa.overall_score,
        resolution=summary.resolution_status.value,
    )
except Exception as exc:  # noqa: BLE001 - record any provider failure as evidence
    cause = exc.__cause__ or exc
    evidence.update(
        status="failed",
        error_type=type(exc).__name__,
        cause_type=type(cause).__name__,
        http_status=getattr(cause, "status_code", None),
    )
Path("docs/milestones/1-4/live-llm-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps(evidence))
