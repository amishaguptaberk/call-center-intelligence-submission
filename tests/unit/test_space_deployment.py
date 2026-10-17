import pytest

from scripts.deploy_space import provider_settings, runtime_files


def test_deployment_package_excludes_local_data(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("pass")
    (tmp_path / ".env").write_text("SECRET=private")
    (tmp_path / "db.sqlite3").write_text("private")
    (tmp_path / "report.json").write_text("private")
    assert runtime_files(tmp_path) == ["src/app.py"]


def test_provider_settings_select_only_matching_key(tmp_path):
    config = tmp_path / "settings.env"
    config.write_text("LLM_PROVIDER=groq\nGROQ_API_KEY=test-key\nHF_TOKEN=not-a-runtime-secret\n")
    assert provider_settings(config) == ("groq", "GROQ_API_KEY", "test-key")


def test_missing_provider_secret_prevents_deployment(tmp_path):
    config = tmp_path / "settings.env"
    config.write_text("LLM_PROVIDER=gemini\n")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        provider_settings(config)
