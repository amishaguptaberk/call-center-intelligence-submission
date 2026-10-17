"""Real SQLite transactions behind security audit logging."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from src.database import connection
from src.database.models import AuditLogEntry
from src.security.audit import AuditLogger


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "audit.sqlite3"))
    connection._reset_engine_state()
    connection.init_db()
    yield
    connection._reset_engine_state()


def test_audit_persists_fields_details_and_timestamp(database):
    before = datetime.now(UTC).replace(tzinfo=None)
    AuditLogger().log("call-1", "injection_detected", "app", {"patterns": ["ignore_previous"]})
    AuditLogger().log("call-1", "reviewed", "supervisor")
    with connection.session_scope() as session:
        rows = session.scalars(select(AuditLogEntry).order_by(AuditLogEntry.id)).all()
        assert len(rows) == 2
        assert (rows[0].call_id, rows[0].action, rows[0].user) == (
            "call-1",
            "injection_detected",
            "app",
        )
        assert json.loads(rows[0].details) == {"patterns": ["ignore_previous"]}
        assert before <= rows[0].timestamp <= datetime.now(UTC).replace(tzinfo=None)
        assert rows[1].details is None


def test_failed_transaction_rolls_back_and_closes(database, monkeypatch):
    session = connection.get_session()
    close = Mock(wraps=session.close)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(connection, "get_session", lambda: session)
    with pytest.raises(RuntimeError, match="aborted"):
        with connection.session_scope() as active:
            active.add(AuditLogEntry(call_id="call", action="failed", user="app"))
            active.flush()
            raise RuntimeError("aborted")
    close.assert_called_once()
    with connection.session_scope() as active:
        assert active.scalars(select(AuditLogEntry)).all() == []
    AuditLogger().log("next", "completed", "app")
    with connection.session_scope() as active:
        assert active.scalar(select(AuditLogEntry)).call_id == "next"


def test_commit_failure_rolls_back_and_next_audit_succeeds(database):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with connection.session_scope() as session:
            session.add(AuditLogEntry(call_id="bad", action="failed", user=None))
    AuditLogger().log("good", "completed", "app", {})
    with connection.session_scope() as session:
        rows = session.scalars(select(AuditLogEntry)).all()
        assert len(rows) == 1
        assert rows[0].call_id == "good"
        assert rows[0].details == "{}"
