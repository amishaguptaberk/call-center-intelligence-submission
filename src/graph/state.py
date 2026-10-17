from datetime import datetime
from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class AudioInput(BaseModel):
    audio_data: bytes
    filename: str
    caller_id: str | None = None
    department: str | None = None
    timestamp: datetime | None = Field(default_factory=datetime.now)


class AudioProperties(BaseModel):
    duration_seconds: float
    sample_rate: int
    channels: int


class PIIScanResult(BaseModel):
    pii_detected: bool = False
    affected_fields: list[str] = Field(default_factory=list)


class IntakeResult(BaseModel):
    call_id: str
    validation_passed: bool
    validation_error: str | None = None
    audio_properties: AudioProperties
    pii_scan: PIIScanResult
    temp_file_path: str | None = None


class TranscriptionSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    speaker: str
    confidence: float = Field(ge=0.0, le=1.0)


class TranscriptionResult(BaseModel):
    call_id: str
    full_text: str
    segments: list[TranscriptionSegment] = Field(default_factory=list)
    language: str
    low_confidence_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    flagged_for_review: bool = False


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    ESCALATED = "escalated"


class ActionItem(BaseModel):
    description: str
    owner: str
    deadline: str | None = None


class Entity(BaseModel):
    name: str
    type: str


class SummaryResult(BaseModel):
    call_id: str
    call_purpose: str
    key_discussion_points: list[str] = Field(min_length=3, max_length=7)
    action_items: list[ActionItem] = Field(default_factory=list)
    resolution_status: ResolutionStatus
    sentiment_trajectory: str
    entities: list[Entity] = Field(default_factory=list)


class QADimensionScore(BaseModel):
    dimension: Literal[
        "professionalism",
        "empathy",
        "problem_resolution",
        "compliance",
        "communication_clarity",
    ]
    score: int = Field(ge=1, le=5)
    justification: str
    coaching_tip: str | None = Field(
        default=None,
        description="One concrete, transcript-grounded improvement or reinforcement for this dimension.",
    )


class ComplianceFlag(BaseModel):
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    timestamp_reference: str


class QAScoreResult(BaseModel):
    call_id: str
    dimension_scores: list[QADimensionScore] = Field(min_length=5, max_length=5)
    overall_score: float = Field(ge=1.0, le=5.0)
    compliance_flags: list[ComplianceFlag] = Field(default_factory=list)


class CallReport(BaseModel):
    call_id: str
    intake: IntakeResult
    transcription: TranscriptionResult
    summary: SummaryResult
    qa_scores: QAScoreResult
    created_at: datetime = Field(default_factory=datetime.now)


class InjectionScanResult(BaseModel):
    injection_detected: bool = False
    matched_patterns: list[str] = Field(default_factory=list)


class PIIRedactionResult(BaseModel):
    redacted_text: str
    pii_found: bool = False


class PipelineState(TypedDict, total=False):
    # Original pipeline input
    audio_input: AudioInput

    # Results produced by each stage
    intake: IntakeResult
    transcription: TranscriptionResult  # raw ASR artifact

    # Security results
    injection_scan: InjectionScanResult
    pii_result: PIIRedactionResult
    sanitized_transcription: TranscriptionResult  # safe downstream version

    summary: SummaryResult
    qa_scores: QAScoreResult
    report: CallReport

    # Workflow/control information
    error: str
    status: str
