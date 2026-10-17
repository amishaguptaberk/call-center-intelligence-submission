import pytest

from src.utils.config import load_config


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    # Tests must not depend on a developer's .env or real credentials.
    monkeypatch.setattr("src.utils.config.load_dotenv", lambda: None)
    for name in (
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "WHISPER_MODEL_SIZE",
        "CONFIDENCE_THRESHOLD",
        "LOW_CONFIDENCE_HALT_RATIO",
        "DB_PATH",
        "DB_ENCRYPTION_KEY",
        "MAX_RETRIES_PER_NODE",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_load_config_rejects_invalid_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unsupported")
    with pytest.raises(ValueError, match="Invalid LLM provider"):
        load_config()


def test_defaults():
    config = load_config()
    assert config.llm_provider == "openai"
    assert config.whisper_model_size == "base"
    assert config.confidence_threshold == 0.5
    assert config.low_confidence_halt_ratio == 0.5
    assert config.db_path == "data/db.sqlite3"
    assert config.max_retries_per_node == 3
    assert config.llm_timeout_seconds == 30


@pytest.mark.parametrize(
    "provider,key",
    [
        ("openai", "OPENAI_API_KEY"),
        ("gemini", "GOOGLE_API_KEY"),
        ("groq", "GROQ_API_KEY"),
    ],
)
def test_supported_provider_with_its_key(monkeypatch, provider, key):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv(key, "test-provider-key")
    assert load_config().llm_provider == provider


@pytest.mark.parametrize(
    "provider,key",
    [
        ("openai", "OPENAI_API_KEY"),
        ("gemini", "GOOGLE_API_KEY"),
        ("groq", "GROQ_API_KEY"),
    ],
)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_selected_provider_requires_nonblank_key(monkeypatch, provider, key, value):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    if value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        load_config()


@pytest.mark.parametrize(
    "name,value",
    [
        ("CONFIDENCE_THRESHOLD", "-0.01"),
        ("CONFIDENCE_THRESHOLD", "1.01"),
        ("LOW_CONFIDENCE_HALT_RATIO", "-0.01"),
        ("LOW_CONFIDENCE_HALT_RATIO", "1.01"),
        ("MAX_RETRIES_PER_NODE", "-1"),
        ("MAX_RETRIES_PER_NODE", "0"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_TIMEOUT_SECONDS", "-1"),
        ("CONFIDENCE_THRESHOLD", "invalid"),
        ("MAX_RETRIES_PER_NODE", "1.5"),
    ],
)
def test_invalid_numeric_configuration(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        load_config()


@pytest.mark.parametrize("boundary", ["0", "1"])
def test_probability_boundaries_and_one_attempt_are_valid(monkeypatch, boundary):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", boundary)
    monkeypatch.setenv("LOW_CONFIDENCE_HALT_RATIO", boundary)
    monkeypatch.setenv("MAX_RETRIES_PER_NODE", "1")
    config = load_config()
    assert config.confidence_threshold == float(boundary)
    assert config.low_confidence_halt_ratio == float(boundary)
    assert config.max_retries_per_node == 1


def test_environment_overrides_and_secret_repr(monkeypatch):
    for name, value in {
        "WHISPER_MODEL_SIZE": "small",
        "DB_PATH": "custom.sqlite3",
        "CONFIDENCE_THRESHOLD": "0.8",
        "LOW_CONFIDENCE_HALT_RATIO": "0.2",
        "MAX_RETRIES_PER_NODE": "5",
        "LLM_TIMEOUT_SECONDS": "60",
        "OPENAI_API_KEY": "secret-openai",
        "GOOGLE_API_KEY": "secret-google",
        "GROQ_API_KEY": "secret-groq",
        "DB_ENCRYPTION_KEY": "secret-db",
    }.items():
        monkeypatch.setenv(name, value)
    config = load_config()
    assert (config.whisper_model_size, config.db_path) == ("small", "custom.sqlite3")
    assert (config.confidence_threshold, config.low_confidence_halt_ratio) == (0.8, 0.2)
    assert (config.max_retries_per_node, config.llm_timeout_seconds) == (5, 60)
    assert config.db_encryption_key == "secret-db"
    for secret in ("secret-openai", "secret-google", "secret-groq", "secret-db"):
        assert secret not in repr(config)


def test_config_is_frozen_and_loads_model_override(monkeypatch):
    from dataclasses import FrozenInstanceError

    monkeypatch.setenv("LLM_MODEL", "test-model")
    config = load_config()
    assert config.llm_model == "test-model"
    with pytest.raises(FrozenInstanceError):
        config.llm_provider = "groq"


def test_dotenv_loading(monkeypatch, tmp_path):
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("WHISPER_MODEL_SIZE=tiny\nLLM_TIMEOUT_SECONDS=90\n")
    monkeypatch.setattr("src.utils.config.load_dotenv", lambda: load_dotenv(env_file))
    config = load_config()
    assert config.whisper_model_size == "tiny"
    assert config.llm_timeout_seconds == 90


def test_required_packages_and_environment_example():
    from pathlib import Path

    from dotenv import dotenv_values

    root = Path(__file__).resolve().parents[2]
    for package in (
        "agents",
        "graph",
        "security",
        "services",
        "ui",
        "database",
        "utils",
    ):
        assert (root / "src" / package / "__init__.py").is_file()
    values = dotenv_values(root / ".env.example")
    assert {
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "WHISPER_MODEL_SIZE",
        "CONFIDENCE_THRESHOLD",
        "LOW_CONFIDENCE_HALT_RATIO",
        "DB_PATH",
        "DB_ENCRYPTION_KEY",
        "MAX_RETRIES_PER_NODE",
        "LLM_TIMEOUT_SECONDS",
    } <= values.keys()
    assert not values["LLM_MODEL"]
