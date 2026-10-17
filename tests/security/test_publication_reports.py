import json
from pathlib import Path


def test_shareable_failure_mode_examples_omit_call_text():
    report_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation/reports/heuristic_all10_failure_modes.json"
    )
    report = json.loads(report_path.read_text())
    examples = [
        example
        for recording in report["per_file"].values()
        for category in recording["examples"].values()
        for example in category
    ]

    assert len(report["per_file"]) == 10
    assert len(examples) == 73
    assert all(not example.get("text") for example in examples), (
        "Shareable failure-mode examples must omit raw call text"
    )
    assert all({"i", "t", "label", "reason"} <= example.keys() for example in examples)
    assert "omitted" in report["note"].lower()
