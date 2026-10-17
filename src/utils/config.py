import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    llm_provider: str
    openai_api_key: str | None = field(repr=False)
    google_api_key: str | None = field(repr=False)
    groq_api_key: str | None = field(repr=False)
    whisper_model_size: str
    confidence_threshold: float
    low_confidence_halt_ratio: float
    db_path: str
    db_encryption_key: str | None = field(repr=False)
    max_retries_per_node: int
    llm_timeout_seconds: int
    llm_model: str | None = None


def load_config(*, require_provider_key: bool = True) -> Config:
    load_dotenv()
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")
    whisper_model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    low_confidence_halt_ratio = float(os.getenv("LOW_CONFIDENCE_HALT_RATIO", "0.5"))
    db_path = os.getenv("DB_PATH", "data/db.sqlite3")
    db_encryption_key = os.getenv("DB_ENCRYPTION_KEY")
    max_retries_per_node = int(os.getenv("MAX_RETRIES_PER_NODE", "3"))
    llm_timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    if not (0 <= confidence_threshold <= 1):
        raise ValueError(f"Invalid confidence threshold: {confidence_threshold}")
    if not (0 <= low_confidence_halt_ratio <= 1):
        raise ValueError(f"Invalid low confidence halt ratio: {low_confidence_halt_ratio}")
    if not (1 <= max_retries_per_node):
        raise ValueError(f"Invalid max retries per node: {max_retries_per_node}")
    if not (0 < llm_timeout_seconds):
        raise ValueError(f"Invalid LLM timeout seconds: {llm_timeout_seconds}")

    if llm_provider not in ["openai", "gemini", "groq"]:
        raise ValueError(f"Invalid LLM provider: {llm_provider}")
    if (
        require_provider_key
        and llm_provider == "openai"
        and (not openai_api_key or not openai_api_key.strip())
    ):
        raise ValueError("OPENAI_API_KEY is not set")
    if (
        require_provider_key
        and llm_provider == "gemini"
        and (not google_api_key or not google_api_key.strip())
    ):
        raise ValueError("GOOGLE_API_KEY is not set")
    if (
        require_provider_key
        and llm_provider == "groq"
        and (not groq_api_key or not groq_api_key.strip())
    ):
        raise ValueError("GROQ_API_KEY is not set")

    return Config(
        llm_provider=llm_provider,
        openai_api_key=openai_api_key,
        google_api_key=google_api_key,
        groq_api_key=groq_api_key,
        whisper_model_size=whisper_model_size,
        confidence_threshold=confidence_threshold,
        low_confidence_halt_ratio=low_confidence_halt_ratio,
        db_path=db_path,
        db_encryption_key=db_encryption_key,
        max_retries_per_node=max_retries_per_node,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_model=os.getenv("LLM_MODEL") or None,
    )


def temp_file_retention() -> int:
    value = int(os.getenv("TEMP_FILE_RETENTION", "50"))
    if value < 1:
        raise ValueError("TEMP_FILE_RETENTION must be a positive integer")
    return value
