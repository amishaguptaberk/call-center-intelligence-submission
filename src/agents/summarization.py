import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import SummaryResult, TranscriptionResult
from src.utils.config import load_config
from src.utils.formatters import secs_to_mmss
from src.utils.llm_factory import get_llm

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    pass


def summarize(transcript: TranscriptionResult) -> SummaryResult:
    config = load_config()
    llm = get_llm(
        provider=config.llm_provider,
        model=config.llm_model,
        timeout=config.llm_timeout_seconds,
    )

    structured_llm = llm.with_structured_output(SummaryResult)

    system_prompt = "You are a call-center conversation analyst. Summarize the provided transcript accurately and concisely. Use only information explicitly supported by the transcript. Do not invent facts, entities, action items, or outcomes. If information is unclear or absent, reflect that uncertainty rather than guessing."

    segments = transcript.segments
    full_text = []

    for segment in segments:
        text = f"[{secs_to_mmss(segment.start_time)}-{secs_to_mmss(segment.end_time)}] {segment.speaker}: {segment.text}"
        full_text.append(text)

    formatted_transcript = "\n".join(full_text)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Summarize the following call-center transcript:\n\n{formatted_transcript}"
        ),
    ]
    for attempt in range(config.max_retries_per_node):
        try:
            result = structured_llm.invoke(messages)
            result.call_id = transcript.call_id
            return result
        except Exception as e:
            if attempt == config.max_retries_per_node - 1:
                raise SummarizationError(
                    "Failed to summarize transcript"
                ) from e  # tells us at which point of the pipeline we have an error
            delay = min(2**attempt, 10)
            logger.warning(
                "Analysis retry",
                extra={
                    "node": "summarization",
                    "attempt": attempt + 1,
                    "error_type": type(e).__name__,
                },
            )
            time.sleep(delay)
