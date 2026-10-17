import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI


def get_llm(provider: str | None = None, model: str | None = None, timeout: int = 30):
    load_dotenv()
    provider = provider or os.getenv("LLM_PROVIDER", "openai")
    model = model or os.getenv("LLM_MODEL") or None
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    if not 0 <= temperature <= 2:
        raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
    if provider == "openai":
        selected_model = model if model is not None else "gpt-4o"
        return ChatOpenAI(
            model=selected_model,
            timeout=timeout,
            max_retries=0,
            temperature=temperature,
        )

    elif provider == "gemini":
        selected_model = model if model is not None else "gemini-3.6-flash"
        return ChatGoogleGenerativeAI(
            model=selected_model,
            timeout=timeout,
            max_retries=0,
            temperature=temperature,
        )

    elif provider == "groq":
        selected_model = model if model is not None else "llama-3.3-70b-versatile"
        return ChatGroq(
            model=selected_model,
            timeout=timeout,
            max_retries=0,
            temperature=temperature,
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
