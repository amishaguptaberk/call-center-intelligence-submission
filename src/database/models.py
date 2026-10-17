from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TranscriptionCache(Base):
    __tablename__ = "transcription_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    audio_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    transcription_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)

    call_id: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    user: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class CallRecord(Base):
    __tablename__ = "call_records"

    id: Mapped[int] = mapped_column(primary_key=True)

    call_id: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String, default="completed", nullable=False)
    audio_filename: Mapped[str | None] = mapped_column(String, nullable=True)

    transcript_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    summary_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    qa_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    report_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


CallAnalysis = CallRecord
