from unittest.mock import MagicMock

import pytest

from src.agents import qa_scoring, summarization
from src.graph.state import (
    QADimensionScore,
    QAScoreResult,
    SummaryResult,
    TranscriptionResult,
    TranscriptionSegment,
)
from src.utils import llm_factory
from src.utils.formatters import format_qa, secs_to_mmss


def transcript():
    return TranscriptionResult(
        call_id="current",
        language="en",
        full_text="Hello. Done.",
        segments=[
            TranscriptionSegment(
                start_time=0,
                end_time=1,
                text="Hello.",
                speaker="Customer",
                confidence=1,
            ),
            TranscriptionSegment(
                start_time=90, end_time=91, text="Done.", speaker="Agent", confidence=1
            ),
        ],
    )


def summary():
    return SummaryResult(
        call_id="current",
        call_purpose="Distinct purpose",
        key_discussion_points=["One", "Two", "Three"],
        resolution_status="resolved",
        sentiment_trajectory="neutral",
    )


def scores():
    return QAScoreResult(
        call_id="wrong",
        overall_score=3,
        dimension_scores=[
            QADimensionScore(
                dimension=name,
                score=5,
                justification="At 01:30, completed the request.",
            )
            for name in qa_scoring.DIMENSION_WEIGHTS
        ],
    )


@pytest.mark.parametrize(
    "provider,adapter,default",
    [
        ("openai", "ChatOpenAI", "gpt-4o"),
        ("gemini", "ChatGoogleGenerativeAI", "gemini-3.6-flash"),
        ("groq", "ChatGroq", "llama-3.3-70b-versatile"),
    ],
)
def test_factory_selection_defaults_override_timeout(monkeypatch, provider, adapter, default):
    monkeypatch.setattr(llm_factory, "load_dotenv", lambda: None)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    constructor = MagicMock()
    monkeypatch.setattr(llm_factory, adapter, constructor)
    assert llm_factory.get_llm(timeout=17) is constructor.return_value
    constructor.assert_called_once_with(model=default, timeout=17, max_retries=0, temperature=0)
    llm_factory.get_llm(provider, model="custom", timeout=19)
    constructor.assert_called_with(model="custom", timeout=19, max_retries=0, temperature=0)
    monkeypatch.setenv("LLM_MODEL", "environment-model")
    llm_factory.get_llm()
    constructor.assert_called_with(
        model="environment-model", timeout=30, max_retries=0, temperature=0
    )


@pytest.mark.parametrize(
    "module,error,result",
    [
        (summarization, summarization.SummarizationError, summary),
        (qa_scoring, qa_scoring.QAScoringError, scores),
    ],
)
@pytest.mark.parametrize("attempts", [3, 7])
def test_analysis_contracts_and_backoff(monkeypatch, module, error, result, attempts):
    config = MagicMock(
        llm_provider="groq",
        llm_model="custom",
        llm_timeout_seconds=17,
        max_retries_per_node=attempts,
    )
    factory = MagicMock()
    structured = factory.return_value.with_structured_output.return_value
    sleep = MagicMock()
    monkeypatch.setattr(module, "load_config", lambda: config)
    monkeypatch.setattr(module, "get_llm", factory)
    monkeypatch.setattr(module.time, "sleep", sleep)

    def invoke():
        if module is summarization:
            return module.summarize(transcript())
        return module.score_qa(transcript(), summary())

    structured.invoke.side_effect = [RuntimeError("transient")] * (attempts - 1) + [result()]
    actual = invoke()
    assert actual.call_id == "current"
    assert structured.invoke.call_count == attempts
    assert [c.args[0] for c in sleep.call_args_list] == [min(2**i, 10) for i in range(attempts - 1)]
    factory.assert_called_once_with(provider="groq", model="custom", timeout=17)
    factory.return_value.with_structured_output.assert_called_once_with(
        SummaryResult if module is summarization else QAScoreResult
    )
    messages = structured.invoke.call_args.args[0]
    assert "[00:00-00:01] Customer: Hello.\n[01:30-01:31] Agent: Done." in messages[1].content
    if module is qa_scoring:
        assert actual.overall_score == 5
        assert summary().model_dump_json(indent=2) in messages[1].content
        prompt = messages[0].content
        for name in qa_scoring.DIMENSION_WEIGHTS:
            rubric = prompt.split(name.upper() + ": ")[1].split("JUSTIFICATIONS:")[0]
            for value in range(1, 6):
                assert f"{value} = " in rubric
        for phrase in [
            "3 represents competent",
            "Do not inflate",
            "MM:SS",
            "real QA coach",
            "genuine procedural",
            "Do not penalize a call merely because it is short",
        ]:
            assert phrase in prompt
    structured.invoke.reset_mock()
    sleep.reset_mock()
    structured.invoke.side_effect = RuntimeError("unavailable")
    with pytest.raises(error):
        invoke()
    assert structured.invoke.call_count == attempts
    assert sleep.call_count == attempts - 1


@pytest.mark.parametrize(
    "names",
    [
        ["professionalism"] * 5,
        ["professionalism", "empathy", "problem_resolution", "compliance", "invented"],
    ],
)
def test_qa_rejects_duplicate_or_unknown_dimensions(monkeypatch, names):
    invalid = scores()
    for dimension, name in zip(invalid.dimension_scores, names):
        dimension.dimension = name
    factory = MagicMock()
    factory.return_value.with_structured_output.return_value.invoke.return_value = invalid
    monkeypatch.setattr(qa_scoring, "load_config", lambda: MagicMock(max_retries_per_node=1))
    monkeypatch.setattr(qa_scoring, "get_llm", factory)
    with pytest.raises(qa_scoring.QAScoringError) as caught:
        qa_scoring.score_qa(transcript(), summary())
    assert "exactly once" in str(caught.value.__cause__)


def test_formatter_required_empty_case_and_boundaries():
    assert "No compliance issues detected." in format_qa(scores())
    assert [secs_to_mmss(value) for value in (0, 59.99, 60, 90, 3600)] == [
        "00:00",
        "00:59",
        "01:00",
        "01:30",
        "60:00",
    ]


@pytest.mark.parametrize(
    "provider,adapter",
    [
        ("openai", "ChatOpenAI"),
        ("gemini", "ChatGoogleGenerativeAI"),
        ("groq", "ChatGroq"),
    ],
)
def test_real_provider_adapter_constructs_without_network(monkeypatch, provider, adapter):
    monkeypatch.setattr(llm_factory, "load_dotenv", lambda: None)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for key in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.setenv(key, "synthetic-test-key")
    assert isinstance(llm_factory.get_llm(provider, timeout=17), getattr(llm_factory, adapter))
