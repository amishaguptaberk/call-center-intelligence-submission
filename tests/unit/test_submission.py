import os
import subprocess
import sys
import tomllib
from pathlib import Path

from src.ui.app import build_app, build_theme

ROOT = Path(__file__).resolve().parents[2]


def test_project_metadata_declares_python_311_support():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert metadata["project"]["requires-python"] == ">=3.11,<3.12"


def test_transcription_import_does_not_require_provider_credentials():
    environment = dict(os.environ)
    for key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        environment[key] = ""
    result = subprocess.run(
        [sys.executable, "-c", "import src.agents.transcription"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_submission_has_both_tabs_and_copyable_transcript():
    app = build_app()
    components = app.config["components"]
    tabs = [item["props"].get("label") for item in components if item["type"] == "tabitem"]
    assert tabs == ["Analyze call", "All MP3 History", "Observability"]
    transcript = next(item for item in components if item["props"].get("label") == "Transcript")
    assert "copy" in transcript["props"]["buttons"]
    assert build_theme().to_dict()["theme"]["body_text_color"] == "#17212b"


def test_container_includes_samples_and_starts_gradio():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY data/samples ./data/samples" in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert 'CMD ["python", "app.py"]' in dockerfile


def test_ci_runs_bounded_container_build_and_persistence_smoke():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/checks.yml").read_text())
    job = workflow["jobs"]["container"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] <= 30
    script = "\n".join(step.get("run", "") for step in job["steps"])
    for required in (
        "set -euo pipefail",
        "docker build",
        "docker run",
        "docker exec",
        "ffmpeg -version",
        "/config",
        "os.getuid() != 0",
        "sqlite3.connect",
        "docker rm -f",
        "docker volume rm",
        "WHISPER_PRELOAD=false",
        "timeout 1200",
        'docker exec -i "$container" python - < scripts/container_smoke.py',
        'docker exec -i "$container" python - --check-persistence < scripts/container_smoke.py',
        'assert [item["props"].get("label") for item in c["components"] '
        'if item["type"] == "tabitem"] == '
        '["Analyze call", "All MP3 History", "Observability"]',
    ):
        assert required in script
    assert script.count("\nready\n") == 2


def test_database_initializes_without_model_credentials(tmp_path, monkeypatch):
    import pytest

    from src.database import connection
    from src.utils.config import load_config

    monkeypatch.setattr("src.utils.config.load_dotenv", lambda: None)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "submission.sqlite3"))
    connection._reset_engine_state()
    try:
        connection.init_db()
        assert (tmp_path / "submission.sqlite3").exists()
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            load_config()
    finally:
        connection._reset_engine_state()
