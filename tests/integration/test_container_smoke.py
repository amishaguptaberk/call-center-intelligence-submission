import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("stdin_mode", [False, True])
def test_synthetic_container_pipeline_and_reopened_exports(tmp_path, stdin_mode):
    environment = dict(os.environ)
    environment.update(
        DB_PATH=str(tmp_path / "synthetic.sqlite3"),
        OPENAI_API_KEY="",
        GOOGLE_API_KEY="",
        GROQ_API_KEY="",
        HF_HUB_OFFLINE="1",
        WHISPER_PRELOAD="false",
    )
    outputs = []
    for flags in ([], ["--check-persistence"]):
        command = [sys.executable, "-" if stdin_mode else "-m"]
        if not stdin_mode:
            command.append("scripts.container_smoke")
        result = subprocess.run(
            command + flags,
            input=(ROOT / "scripts/container_smoke.py").read_text() if stdin_mode else None,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        outputs.append(json.loads(result.stdout.splitlines()[-1]))
    assert outputs[0]["call_id"] == outputs[1]["call_id"]
    assert outputs[0]["synthetic_fixture"] is True
    assert outputs[1]["persistence_verified"] is True
    assert outputs[1]["overall_score"] == 3.0
    with sqlite3.connect(environment["DB_PATH"]) as db:
        rows = db.execute(
            "SELECT call_id, transcript_text, report_json FROM call_records"
        ).fetchall()
        actions = {row[0] for row in db.execute("SELECT action FROM audit_log")}
    assert len(rows) == 1
    assert rows[0][0] == outputs[0]["call_id"]
    assert "[REDACTED_PHONE]" in rows[0][1]
    assert "fixture@example.com" not in rows[0][2]
    assert {"started", "completed"} <= actions
